from io import BytesIO
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageStat

from bender_voice.hardware import Hardware, HardwareError
from bender_voice.photo_enhancement import enhance_photo
from hardware_api import build_hardware_router, get_hardware
from voice_api import get_voice


def jpeg(image):
    output=BytesIO();image.save(output,format='JPEG',quality=90);return output.getvalue()


def gradient(low,high):
    image=Image.new('RGB',(256,64))
    image.putdata([(round(low+(high-low)*x/255),)*3 for y in range(64) for x in range(256)])
    return jpeg(image)


def average(data):
    with Image.open(BytesIO(data)) as image:return ImageStat.Stat(image.convert('L')).mean[0]


class PhotoEnhancementTests(unittest.TestCase):
    def test_bright_and_dark_photos_get_opposite_gentle_corrections(self):
        bright=gradient(150,250);dark=gradient(10,90)
        corrected,report=enhance_photo(bright)
        self.assertLess(average(corrected),average(bright))
        self.assertLess(average(bright)-average(corrected),40)
        self.assertGreater(report['gamma'],1)
        corrected,report=enhance_photo(dark)
        self.assertGreater(average(corrected),average(dark))
        self.assertLess(average(corrected)-average(dark),40)
        self.assertLess(report['gamma'],1)

    def test_saturated_or_black_uniform_photos_do_not_gain_invented_detail(self):
        for color in ('white','black'):
            result,report=enhance_photo(jpeg(Image.new('RGB',(64,48),color)))
            with Image.open(BytesIO(result)) as image:
                self.assertEqual(image.size,(64,48))
                self.assertEqual(image.convert('L').getextrema(),(255,255) if color=='white' else (0,0))
            self.assertTrue(report['warnings']);self.assertEqual(report['operations'],[])

    def test_color_regions_and_dimensions_are_preserved(self):
        image=Image.new('RGB',(100,60),(220,25,25));image.paste((25,200,25),(50,0,100,60))
        result,report=enhance_photo(jpeg(image))
        with Image.open(BytesIO(result)) as corrected:
            r,g,b=corrected.getpixel((25,30));self.assertGreater(r,g)
            r,g,b=corrected.getpixel((75,30));self.assertGreater(g,r)
            self.assertEqual(corrected.size,image.size)
        self.assertEqual((report['width'],report['height']),image.size)

    def test_invalid_inputs_are_rejected_before_analysis(self):
        for data in (b'',b'bad-jpeg',b'x'*4_000_001):
            with self.subTest(length=len(data)),self.assertRaises(HardwareError):enhance_photo(data)
        output=BytesIO();Image.new('RGB',(10,10)).save(output,format='PNG')
        with self.assertRaises(HardwareError):enhance_photo(output.getvalue())

    def test_each_preparation_uses_the_original_without_accumulating_corrections(self):
        with tempfile.TemporaryDirectory() as directory:
            hardware=Hardware({'data_dir':directory});identifier='a'*32;source=gradient(160,250)
            hardware.photo_path(identifier).write_bytes(source)
            first=hardware.prepare_photo(identifier);second=hardware.prepare_photo(identifier)
            self.assertEqual(first['image'],second['image'])
            self.assertEqual(hardware.photo_path(identifier).read_bytes(),source)
            self.assertEqual(hardware.enhanced_photo_path(identifier).read_bytes(),first['image'])
            self.assertNotEqual(source,first['image'])
            with self.assertRaises(ValueError):hardware.prepare_photo('../secret')

    def test_capture_preview_and_vision_use_exactly_the_same_corrected_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            hardware=Hardware({'data_dir':directory});identifier='b'*32;source=gradient(160,250)
            hardware.photo_path(identifier).write_bytes(source)
            brain=Mock(return_value='Une pièce lumineuse.');voice=Mock();voice.prepare.return_value={'segments':[]}
            app=FastAPI();app.include_router(build_hardware_router(brain))
            app.dependency_overrides[get_hardware]=lambda:hardware
            app.dependency_overrides[get_voice]=lambda:voice
            headers={'X-Bender-Control-Token':hardware.control_token()}
            capture=dict(id=identifier,image_url=f'/api/hardware/photos/{identifier}',width=256,height=64)
            with TestClient(app) as client,patch.object(hardware,'capture',return_value=capture):
                self.assertEqual(client.get(f'/api/hardware/photos/{identifier}/enhanced').status_code,403)
                data=client.post('/api/hardware/camera',headers=headers).json()
                self.assertTrue(data['enhancement']['enabled'])
                original=client.get(data['original_image_url'],headers=headers)
                preview=client.get(data['image_url'],headers=headers)
                self.assertEqual(original.content,source);self.assertNotEqual(preview.content,source)
                response=client.post('/api/hardware/vision',headers=headers,json={'photo_id':identifier,'question':'Que vois-tu ?'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(brain.call_args.args,('Que vois-tu ?',preview.content))
                # The original JPEG is still there and the corrected endpoint is private.
                self.assertEqual(hardware.photo_path(identifier).read_bytes(),source)

    def test_retention_keeps_three_originals_and_their_corrected_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            hardware=Hardware({'data_dir':directory});source=gradient(120,230)
            def capture(args,**kwargs):Path(args[-1]).write_bytes(source)
            with patch('shutil.which',return_value='ffmpeg'),patch.object(hardware.camera,'prepare',return_value=('640x480',[])),patch('subprocess.run',side_effect=capture):
                for _ in range(5):
                    photo=hardware.capture();hardware.prepare_photo(photo['id'])
            images=list(hardware.root.glob('snapshot-*.jpg'))
            originals=[p for p in images if re.fullmatch(r'snapshot-[a-f0-9]{32}\.jpg',p.name)]
            self.assertEqual(len(originals),3);self.assertEqual(len(images),6)
            self.assertTrue(all(p.with_name(p.stem+'-enhanced.jpg').is_file() for p in originals))
