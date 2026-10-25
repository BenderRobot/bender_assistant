import tempfile
import sqlite3
from contextlib import closing
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
            self.assertTrue(initial['s1-t3']['done'])
            for key, done in [('s0-t1', False), ('s1-t3', False), ('s2-t1', True)]:
                result = client.put(f'/api/roadmap/tasks/{key}', json={'done': done})
                self.assertEqual(result.status_code, 200)
                self.assertIsNotNone(result.json()['updated_at'])
            progress = self.client(path).get('/api/roadmap').json()['progress']
            self.assertFalse(progress['s0-t1']['done'])
            self.assertFalse(progress['s1-t3']['done'])
            self.assertTrue(progress['s2-t1']['done'])
            self.assertTrue(progress['s2-t2']['done'])

    def test_updated_plan_separates_implemented_scenarios_from_robot_validation(self):
        self.assertEqual(PLAN['version'],'2026-10-25')
        self.assertTrue(TASKS['s3-t20']['initial_done'])
        self.assertFalse(TASKS['s3-t21']['initial_done'])
        self.assertFalse(TASKS['s3-t23']['initial_done'])
        self.assertFalse(TASKS['s5-t8']['initial_done'])
        self.assertFalse(TASKS['s5-t9']['initial_done'])
        self.assertFalse(TASKS['s7-t7']['initial_done'])
        for task in TASKS.values():
            self.assertTrue(task['guide']['steps'])
            self.assertTrue(task['guide']['expected'])

    def test_invalid_input_and_cross_origin_write_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.client(Path(directory) / 'roadmap.sqlite3')
            self.assertEqual(client.put('/api/roadmap/tasks/missing', json={'done': True}).status_code, 404)
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': 'false'}).status_code, 422)
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': False}, headers={'Origin': 'https://other.example'}).status_code, 403)
            self.assertTrue(client.get('/api/roadmap').json()['progress']['s0-t1']['done'])
            self.assertEqual(client.put('/api/roadmap/tasks/s0-t1', json={'done': False}, headers={'Origin': 'http://testserver'}).status_code, 200)

    def test_existing_checklist_migrates_and_step_notes_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'roadmap.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                with connection:
                    connection.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY, done INTEGER NOT NULL, updated_at TEXT NOT NULL)')
                    connection.execute("INSERT INTO tasks VALUES ('s1-t3', 1, 'existing')")
            client = self.client(path)
            initial = client.get('/api/roadmap').json()
            self.assertTrue(initial['progress']['s1-t3']['done'])
            self.assertIn('attente', initial['steps']['step-5']['notes'])
            note = 'CAO validée. Composants non reçus : attendre pour le montage.'
            self.assertEqual(client.patch('/api/roadmap/steps/step-5', json={'notes': note}).status_code, 200)
            self.assertEqual(client.patch('/api/roadmap/steps/step-5', json={'status': 'testing'}).status_code, 200)
            result = self.client(path).get('/api/roadmap').json()
            self.assertEqual(result['steps']['step-5']['notes'], note)
            self.assertEqual(result['steps']['step-5']['status'], 'testing')
            self.assertFalse(result['progress']['s5-t2']['done'])
            self.assertTrue(result['progress']['s1-t3']['done'])
            self.assertEqual(client.patch('/api/roadmap/steps/step-5', json={'notes': ''}).status_code, 200)
            result = client.get('/api/roadmap').json()
            self.assertEqual(result['steps']['step-5']['notes'], '')
            self.assertEqual(result['steps']['step-5']['status'], 'testing')

    def test_invalid_step_updates_and_foreign_origin_do_not_change_state(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.client(Path(directory) / 'roadmap.sqlite3')
            self.assertEqual(client.patch('/api/roadmap/steps/missing', json={'status': 'todo'}).status_code, 404)
            for change in ({'status': 'bad'}, {'notes': 'x' * 8001}, {}, {'notes': None}, {'status': None}):
                self.assertEqual(client.patch('/api/roadmap/steps/step-5', json=change).status_code, 422)
            before = client.get('/api/roadmap').json()['steps']['step-5']
            self.assertEqual(client.patch('/api/roadmap/steps/step-5', json={'notes': 'changed'}, headers={'Origin': 'https://other.example'}).status_code, 403)
            self.assertEqual(client.get('/api/roadmap').json()['steps']['step-5'], before)
