"""Shared project checklist. Progress lives in data/, outside Git and releases."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'roadmap-plan.json').read_text(encoding='utf-8'))
TASKS = {task['id']: task for step in PLAN['steps'] for task in step['tasks']}
STEPS = {step['id']: step for step in PLAN['steps']}


class StepUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=8000)
    status: Literal['todo', 'in_progress', 'testing', 'validated'] | None = None


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
                connection.execute('CREATE TABLE IF NOT EXISTS steps (id TEXT PRIMARY KEY, notes TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT)')
                for step in PLAN['steps']:
                    default_status = step.get('initial_status', 'in_progress' if any(t.get('initial_done') for t in step['tasks']) else 'todo')
                    connection.execute('INSERT OR IGNORE INTO steps VALUES (?, ?, ?, NULL)',
                                       (step['id'], step.get('initial_notes', ''), default_status))
                yield connection
        finally:
            connection.close()

    @router.get('')
    def read_plan():
        with connect() as connection:
            rows = connection.execute('SELECT id, done, updated_at FROM tasks').fetchall()
            stage_rows = connection.execute('SELECT id, notes, status, updated_at FROM steps').fetchall()
        overrides = {key: {'done': bool(done), 'updated_at': updated} for key, done, updated in rows if key in TASKS}
        return {'plan': PLAN, 'steps': {
            key: {'notes': notes, 'status': status, 'updated_at': updated}
            for key, notes, status, updated in stage_rows if key in STEPS
        }, 'progress': {
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

    @router.patch('/steps/{step_id}')
    def update_step(step_id: str, update: StepUpdate, request: Request):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Modification autorisée depuis Bender uniquement.')
        if step_id not in STEPS:
            raise HTTPException(404, 'Étape inconnue.')
        changes = update.model_dump(exclude_unset=True)
        if not changes or any(value is None for value in changes.values()):
            raise HTTPException(422, 'Fournir une note ou un statut valide.')
        with connect() as connection:
            for field, value in changes.items():
                # Column names only come from the fixed Pydantic schema.
                connection.execute(f"UPDATE steps SET {field}=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id=?", (value, step_id))
            notes, status, updated = connection.execute('SELECT notes, status, updated_at FROM steps WHERE id=?', (step_id,)).fetchone()
        return {'id': step_id, 'notes': notes, 'status': status, 'updated_at': updated}

    return router
