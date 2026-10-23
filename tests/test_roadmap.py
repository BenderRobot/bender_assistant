import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from roadmap_api import PLAN, TASKS, build_roadmap_router


class RoadmapTests(unittest.TestCase):
    def client(self, path):
        app = FastAPI()
        app.include_router(build_roadmap_router(path))
        return TestClient(app)

    def test_stable_unique_actions_and_complete_plan(self):
        ids = [t['id'] for s in PLAN['steps'] for t in s['tasks']]
        self.assertEqual(len(PLAN['steps']), 9)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(s['gate'] and s['tasks'] for s in PLAN['steps']))

    def test_persistence_across_app_restart_and_independent_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data' / 'roadmap.sqlite3'
            client = self.client(path)
            initial = client.get('/api/roadmap').json()['progress']
            self.assertTrue(initial['s0-t1']['done'])
            self.assertFalse(initial['s1-t3']['done'])
            for key, done in [('s0-t1', False), ('s1-t3', True), ('s2-t1', True)]:
                result = client.put(f'/api/roadmap/tasks/{key}', json={'done': done})
                self.assertEqual(result.status_code, 200)
                self.assertIsNotNone(result.json()['updated_at'])
            progress = self.client(path).get('/api/roadmap').json()['progress']
            self.assertFalse(progress['s0-t1']['done'])
            self.assertTrue(progress['s1-t3']['done'])
            self.assertTrue(progress['s2-t1']['done'])
            self.assertFalse(progress['s2-t2']['done'])

    def test_invalid_input_and_cross_origin_write_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.client(Path(directory) / 'roadmap.sqlite3')
            self.assertEqual(client.put('/api/roadmap/tasks/missing', json={'done': True}).status_code, 404)
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': 'false'}).status_code, 422)
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': False}, headers={'Origin': 'https://other.example'}).status_code, 403)
            self.assertTrue(client.get('/api/roadmap').json()['progress']['s0-t1']['done'])
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': False}, headers={'Origin': 'http://testserver'}).status_code, 200)
