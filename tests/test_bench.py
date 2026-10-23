import io
import json
import tarfile
import tempfile
import unittest
import wave
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from bench_api import build_bench_router
from bender_voice.service import VoiceService
from reference_media import install_reference_archive
from voice_api import get_voice, router as voice_router


class BenchTests(unittest.TestCase):
    def test_saved_references_list_and_play_without_synthesis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'references'; media.mkdir()
            with wave.open(str(media / 'test.wav'), 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\x00\x00' * 1600)
            (media / 'test.json').write_text(json.dumps({'cues': [{'t': 0, 'pose': 11}], 'warnings': ['Provisoire']}))
            (media / 'catalog.json').write_text(json.dumps([{'id': 'test', 'title': 'Extrait de test', 'audio': 'test.wav', 'duration': .1, 'methods': {'visual': 'test.json'}}]))
            service = VoiceService({'data_dir': str(root / 'voice'), 'lipsync': {'engine': 'acoustic'}})
            app = FastAPI(); app.include_router(build_bench_router(media)); app.include_router(voice_router)
            app.dependency_overrides[get_voice] = lambda: service
            client = TestClient(app)
            self.assertEqual(client.get('/api/bench/recordings').json()['references'][0]['methods'], ['visual', 'acoustic'])
            response = client.post('/api/bench/references/test/prepare', json={'method': 'visual'})
            self.assertEqual(response.status_code, 200)
            segment = response.json()['segments'][0]
            self.assertEqual(client.get(segment['audio_url']).status_code, 200)
            self.assertEqual(client.get(segment['timeline_url']).json()['cues'][0]['pose'], 11)
            self.assertIn('Provisoire', segment['warnings'])
            self.assertEqual(client.post('/api/bench/references/test/prepare', json={'method': 'acoustic'}).status_code, 200)
            self.assertEqual(client.post('/api/bench/references/test/prepare', json={'method': 'phonemes'}).status_code, 400)
            self.assertEqual(client.post('/api/bench/references/unknown/prepare', json={'method': 'acoustic'}).status_code, 404)

    def test_data_archive_rejects_traversal_symlinks_and_missing_catalog_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'destination'
            target.mkdir(); (target / 'keep.json').write_text('unchanged')
            for name, kind, data in [('../escape.wav', 'file', b'bad'), ('symlink.wav', 'link', b''), ('catalog.json', 'file', b'[{"audio":"missing.wav"}]')]:
                archive_path = root / 'bad.tar.gz'
                with tarfile.open(archive_path, 'w:gz') as archive:
                    member = tarfile.TarInfo(name)
                    if kind == 'link': member.type = tarfile.SYMTYPE; member.linkname = '../escape'
                    else: member.size = len(data)
                    archive.addfile(member, io.BytesIO(data) if kind == 'file' else None)
                with self.assertRaises(ValueError): install_reference_archive(archive_path, target)
                self.assertEqual((target / 'keep.json').read_text(), 'unchanged')
                self.assertFalse((root / 'escape.wav').exists())

    def test_valid_reference_archive_is_installed_without_touching_other_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive_path = root / 'samples.tar.gz'; target = root / 'data' / 'references'
            catalog = json.dumps([{'id': 'test', 'audio': 'test.wav', 'methods': {}}]).encode()
            with tarfile.open(archive_path, 'w:gz') as archive:
                for name, value in [('catalog.json', catalog), ('test.wav', b'wave-content')]:
                    member = tarfile.TarInfo(name); member.size = len(value); archive.addfile(member, io.BytesIO(value))
            self.assertEqual(install_reference_archive(archive_path, target), 1)
            self.assertEqual((target / 'test.wav').read_bytes(), b'wave-content')
