import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_voice.camera import Camera, parse_controls
from bender_voice.hardware import Hardware, HardwareBusy, HardwareError
from hardware_api import build_hardware_router, get_hardware

CONTROLS = '''
User Controls
brightness 0x00980900 (int) : min=-64 max=64 step=1 default=0 value=20
contrast 0x00980901 (int) : min=0 max=64 step=1 default=32 value=60
white_balance_temperature_auto 0x0098090c (bool) : default=1 value=0
privacy 0x009a0910 (bool) : default=0 value=0
Camera Controls
exposure_auto 0x009a0901 (menu) : min=0 max=3 default=3 value=3
  1: Manual Mode
  3: Aperture Priority Mode
exposure_absolute 0x009a0902 (int) : min=5 max=10000 step=1 default=166 value=300 flags=inactive
'''
FORMATS = "[0]: 'YUYV'\n Size: Discrete 640x480\n[1]: 'MJPG' (Motion-JPEG)\n Size: Discrete 1280x720\n Size: Discrete 640x480\n"


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.hardware = Hardware({'data_dir': self.temp.name})
        self.camera = self.hardware.camera

    def tearDown(self): self.temp.cleanup()

    @staticmethod
    def device(*args):
        return SimpleNamespace(stdout=CONTROLS if args[0]=='--list-ctrls-menus' else FORMATS if args[0]=='--list-formats-ext' else '')

    def test_native_controls_and_auto_modes_are_detected(self):
        controls = parse_controls(CONTROLS)
        self.assertNotIn('privacy', controls)
        self.assertEqual(controls['brightness']['min'], -64)
        self.assertTrue(controls['exposure_absolute']['inactive'])
        self.assertEqual(Camera.automatic(controls)['exposure_auto'], 3)
        renamed = parse_controls(CONTROLS.replace('exposure_auto ', 'auto_exposure ').replace('exposure_absolute ', 'exposure_time_absolute '))
        self.assertEqual(Camera.automatic(renamed)['auto_exposure'], 3)

    def test_darker_sets_manual_mode_before_shorter_exposure_and_persists(self):
        with patch('shutil.which', return_value='v4l2-ctl'), patch.object(self.camera, '_run', side_effect=self.device) as command:
            self.camera.update('darker')
            sets = [call.args for call in command.call_args_list if call.args[0]=='--set-ctrl']
        self.assertEqual(sets, [('--set-ctrl','exposure_auto=1'),('--set-ctrl','exposure_absolute=195')])
        restored = Hardware({'data_dir':self.temp.name}).camera.saved()
        self.assertEqual(restored['controls'], {'exposure_auto':1,'exposure_absolute':195})

    def test_auto_resets_contrast_and_removes_old_manual_exposure(self):
        self.camera._save({'exposure_auto':1,'exposure_absolute':500})
        with patch('shutil.which', return_value='v4l2-ctl'), patch.object(self.camera,'_run',side_effect=self.device):
            self.camera.update('auto')
        values = self.camera.saved()['controls']
        self.assertEqual(values['exposure_auto'],3); self.assertEqual(values['contrast'],32)
        self.assertEqual(values['brightness'],0); self.assertEqual(values['white_balance_temperature_auto'],1)
        self.assertNotIn('exposure_absolute',values)

    def test_custom_switch_back_to_auto_clears_stale_manual_time(self):
        self.camera._save({'exposure_auto':1,'exposure_absolute':100})
        with patch('shutil.which',return_value='program'), patch.object(self.camera,'_run',side_effect=self.device) as command:
            self.camera.update('custom',{'exposure_auto':3})
            self.assertNotIn('exposure_absolute',self.camera.saved()['controls'])
            command.reset_mock();self.camera.prepare()
            self.assertFalse(any(call.args==('--set-ctrl','exposure_absolute=100') for call in command.call_args_list))

    def test_unknown_out_of_range_or_injected_controls_never_execute(self):
        with patch('shutil.which',return_value='v4l2-ctl'), patch.object(self.camera,'_run',side_effect=self.device) as command:
            for values in ({'contrast':999},{'contrast;echo':1},{'privacy':0},{'exposure_auto':0}):
                with self.subTest(values=values), self.assertRaises(ValueError): self.camera.update('custom',values)
            self.assertFalse(any(call.args[0]=='--set-ctrl' for call in command.call_args_list))
            self.assertFalse(self.camera.path.exists())
        self.hardware.lock.acquire()
        with self.assertRaises(HardwareBusy): self.camera.update('auto')
        self.hardware.lock.release()

    def test_failed_setting_does_not_save_and_corrupt_file_can_be_reset(self):
        self.camera._save({'contrast':20}); before=self.camera.path.read_bytes()
        def fail(*args):
            if args[0]=='--set-ctrl': raise subprocess.CalledProcessError(1,'v4l2-ctl')
            return self.device(*args)
        with patch('shutil.which',return_value='v4l2-ctl'), patch.object(self.camera,'_run',side_effect=fail):
            with self.assertRaises(HardwareError): self.camera.update('custom',{'contrast':10})
        self.assertEqual(before,self.camera.path.read_bytes())
        self.assertFalse(self.hardware.lock.locked())
        self.camera.path.write_text('broken')
        with patch('shutil.which',return_value='v4l2-ctl'), patch.object(self.camera,'_run',side_effect=self.device):
            self.assertTrue(self.camera.describe()['warnings'])
            self.camera.update('auto')
        self.assertEqual(self.camera.saved()['controls']['exposure_auto'],3)

    def test_hd_capture_waits_for_exposure_and_uses_good_jpeg_quality(self):
        def capture(args,**kwargs):
            self.assertEqual(args[args.index('-video_size')+1],'1280x720')
            self.assertEqual(args[args.index('-vf')+1],r'setpts=PTS-STARTPTS,select=gte(t\,2)')
            self.assertEqual(args[args.index('-q:v')+1],'2')
            Path(args[-1]).write_bytes(b'jpeg')
        with patch('shutil.which',return_value='program'), patch.object(self.camera,'_run',side_effect=self.device), patch('subprocess.run',side_effect=capture):
            result=self.hardware.capture()
        self.assertEqual((result['width'],result['height']),(1280,720))
        self.assertEqual(result['warmup_seconds'],2)

    def test_hd_failure_falls_back_and_missing_controls_do_not_break_capture(self):
        attempts=[]
        def capture(args,**kwargs):
            size=args[args.index('-video_size')+1];attempts.append(size)
            if size=='1280x720':raise subprocess.CalledProcessError(1,'ffmpeg')
            Path(args[-1]).write_bytes(b'jpeg')
        with patch('shutil.which',return_value='program'), patch.object(self.camera,'_run',side_effect=self.device), patch('subprocess.run',side_effect=capture):
            result=self.hardware.capture()
        self.assertEqual(attempts,['1280x720','640x480']);self.assertTrue(result['warnings'])
        with patch('shutil.which',side_effect=lambda name:'ffmpeg' if name=='ffmpeg' else None), patch('subprocess.run',side_effect=capture):
            result=self.hardware.capture()
        self.assertEqual(result['width'],640);self.assertIn('v4l2-ctl',result['warnings'][0])

    def test_camera_settings_api_is_protected_and_validates_native_values(self):
        app=FastAPI();app.include_router(build_hardware_router(lambda *a:'ok'))
        app.dependency_overrides[get_hardware]=lambda:self.hardware
        headers={'X-Bender-Control-Token':self.hardware.control_token()}
        with TestClient(app) as client, patch('shutil.which',return_value='program'), patch.object(self.camera,'_run',side_effect=self.device):
            self.assertEqual(client.get('/api/hardware/camera/settings').status_code,403)
            self.assertEqual(client.post('/api/hardware/camera/settings',json={}).status_code,403)
            self.assertEqual(client.get('/api/hardware/camera/settings',headers=headers).status_code,200)
            self.assertEqual(client.post('/api/hardware/camera/settings',headers=headers,json={'controls':{'contrast':999}}).status_code,400)
            self.assertEqual(client.post('/api/hardware/camera/settings',headers=headers,json={'action':'darker'}).status_code,200)
