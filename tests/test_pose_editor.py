import copy
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pose_api import build_pose_router
from pose_models import EyesShape
from voice_api import router as voice_router


def mouth():
    return {'kind': 'mouth', 'top': [24] * 121, 'bottom': [40] * 121}


def eyes():
    return {'kind': 'eyes', 'eyes': [
        {'cx': cx, 'cy': 240, 'rx': 137, 'ry': 130, 'top': [0, 0, 0], 'bottom': [1, 1, 1]}
        for cx in (244, 556)]}


class PoseEditorTests(unittest.TestCase):
    def client(self, path):
        app = FastAPI(); app.include_router(build_pose_router(path))
        return TestClient(app)

    def test_both_creation_types_survive_restart_and_update_detects_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data' / 'poses.sqlite3'; client = self.client(path)
            created = []
            for name, definition in [('Bouche douce', mouth()), ('Regard curieux', eyes())]:
                response = client.post('/api/poses', json={'name': name, 'definition': definition})
                self.assertEqual(response.status_code, 201); created.append(response.json())
            reopened = self.client(path).get('/api/poses').json()['items']
            self.assertEqual({item['name'] for item in reopened}, {'Bouche douce', 'Regard curieux'})
            original = created[0]; update = {'name': 'Bouche ajustée', 'definition': mouth(), 'revision': original['revision']}
            update['definition']['top'][60] = 20
            saved = client.put('/api/poses/' + original['id'], json=update)
            self.assertEqual(saved.status_code, 200); self.assertEqual(saved.json()['revision'], 2)
            self.assertEqual(client.put('/api/poses/' + original['id'], json=update).status_code, 409)
            self.assertEqual(client.post('/api/poses', json={'name': 'Bouche ajustée', 'definition': mouth()}).status_code, 409)
            latest = self.client(path).get('/api/poses').json()['items']
            self.assertEqual(next(item for item in latest if item['id'] == original['id'])['definition']['top'][60], 20)
            self.assertEqual(len(latest), 2)

    def test_invalid_geometry_code_and_cross_origin_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.client(Path(directory) / 'poses.sqlite3')
            bad = [mouth(), mouth(), mouth(), eyes(), mouth()]
            bad[0]['top'] = [24] * 120
            bad[1]['top'][0] = 70
            bad[2]['script'] = 'alert(1)'
            bad[3]['eyes'][0]['rx'] = -20
            bad[4]['cutoff'] = 100000
            for definition in bad:
                self.assertEqual(client.post('/api/poses', json={'name': 'Test', 'definition': definition}).status_code, 422)
            self.assertEqual(client.post('/api/poses', json={'name': '   ', 'definition': mouth()}).status_code, 422)
            self.assertEqual(client.post('/api/poses', json={'name': 'Test', 'definition': mouth()}, headers={'Origin': 'https://other.example'}).status_code, 403)
            self.assertEqual(client.get('/api/poses').json()['items'], [])

    def test_custom_shapes_travel_through_face_websocket(self):
        app = FastAPI(); app.include_router(voice_router)
        client = TestClient(app)
        with client.websocket_connect('/api/face') as socket:
            socket.send_json({'pose': 0, 'custom_mouth': mouth(), 'custom_eyes': eyes()})
            received = socket.receive_json()
            self.assertEqual(received['custom_mouth']['top'][0], 24)
            self.assertEqual(received['custom_eyes']['eyes'][1]['cx'], 556)
