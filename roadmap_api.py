"""Shared project checklist. Progress lives in data/, outside Git and releases."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StrictBool

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'roadmap-plan.json').read_text(encoding='utf-8'))
TASKS = {task['id']: task for step in PLAN['steps'] for task in step['tasks']}


class TaskUpdate(BaseModel):
    done: StrictBool


def build_roadmap_router(database=None):
    router = APIRouter(prefix='/api/roadmap')
    path = Path(database or os.getenv('BENDER_ROADMAP_DB', str(ROOT / 'data' / 'roadmap.sqlite3')))

    @contextmanager
    def connect():
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10)
        try:
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, done INTEGER NOT NULL, updated_at TEXT NOT NULL)')
                yield connection
        finally:
            connection.close()

    @router.get('')
    def read_plan():
        with connect() as connection:
            rows = connection.execute('SELECT id, done, updated_at FROM tasks').fetchall()
        overrides = {key: {'done': bool(done), 'updated_at': updated} for key, done, updated in rows if key in TASKS}
        return {'plan': PLAN, 'progress': {
            key: overrides.get(key, {'done': task.get('initial_done', False), 'updated_at': None})
            for key, task in TASKS.items()
        }}

    @router.put('/tasks/{task_id}')
    def update_task(task_id: str, update: TaskUpdate, request: Request):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Modification autorisée depuis Bender uniquement.')
        if task_id not in TASKS:
            raise HTTPException(404, 'Action inconnue.')
        with connect() as connection:
            connection.execute("""INSERT INTO tasks VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(id) DO UPDATE SET done=excluded.done, updated_at=excluded.updated_at""",
                (task_id, int(update.done)))
            updated = connection.execute('SELECT updated_at FROM tasks WHERE id=?', (task_id,)).fetchone()[0]
        return {'id': task_id, 'done': update.done, 'updated_at': updated}

    return router
