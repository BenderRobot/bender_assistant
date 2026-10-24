import json
from pathlib import Path
import runpy
import tempfile
import unittest

organizer=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/organize-media.py'))


class OrganizerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.media=self.root/'02_VOIX_ET_ANIMATIONS'
        self.inbox=self.media/'a_importer';self.inbox.mkdir(parents=True)

    def test_verified_reversible_moves_keep_runtime_assets_and_unrelated_downloads(self):
        audio=self.inbox/'original.wav';audio.write_bytes(b'original')
        duplicate=self.media/'montage_elevenlabs'/'extraits'/'original.wav'
        duplicate.parent.mkdir(parents=True);duplicate.write_bytes(b'original')
        video=self.inbox/'video.mp4';video.write_bytes(b'video')
        downloads=self.root/'downloads';downloads.mkdir()
        eleven=downloads/'ElevenLabs_Bender.mp3';eleven.write_bytes(b'voice')
        other=downloads/'ElevenLabs_Audrey.mp3';other.write_bytes(b'other')
        cache=self.root/'bender_assistant'/'data'/'cache.wav';cache.parent.mkdir(parents=True);cache.write_bytes(b'runtime')
        plan=organizer['plan'](self.root,downloads)
        self.assertEqual(len(plan['moves']),4);self.assertEqual(sum(m['duplicate'] for m in plan['moves']),1)
        manifest=self.media/'_archives_rangement'/'manifest.json'
        organizer['apply'](plan,manifest)
        self.assertTrue((self.inbox/'sons_originaux'/'original.wav').is_file())
        self.assertTrue((self.inbox/'videos_originales'/'video.mp4').is_file())
        self.assertTrue((self.inbox/'voix_elevenlabs'/'ElevenLabs_Bender.mp3').is_file())
        self.assertTrue(other.is_file());self.assertEqual(cache.read_bytes(),b'runtime')
        self.assertEqual(organizer['plan'](self.root,downloads)['moves'],[])
        organizer['restore'](manifest)
        for path in (audio,duplicate,video,eleven,other,cache):self.assertTrue(path.is_file())

    def test_name_collision_preserves_distinct_audio_and_changed_plan_is_rejected(self):
        audio=self.inbox/'same.wav';audio.write_bytes(b'new')
        destination=self.inbox/'sons_originaux'/'same.wav';destination.parent.mkdir();destination.write_bytes(b'old')
        plan=organizer['plan'](self.root)
        self.assertNotEqual(Path(plan['moves'][0]['destination']),destination)
        audio.write_bytes(b'changed')
        with self.assertRaises(ValueError):organizer['apply'](plan,self.media/'manifest.json')
        self.assertEqual(destination.read_bytes(),b'old');self.assertTrue(audio.is_file())
