"""User creations never overwrite built-in expressions or validated lip poses."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from pose_models import PoseSave


def build_pose_router(database=None):
    router = APIRouter(prefix='/api/poses')
    path = Path(database or os.getenv('BENDER_POSES_DB', Path(__file__).resolve().parent / 'data' / 'poses.sqlite3'))

    @contextmanager
    def connect():
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10)
        try:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS creations (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                    definition TEXT NOT NULL, revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL, UNIQUE(kind,name))''')
                yield db
        finally: db.close()

    def result(row):
        return dict(zip(('id', 'kind', 'name', 'definition', 'revision', 'updated_at'),
                        (*row[:3], json.loads(row[3]), *row[4:])))

    def origin_check(request):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Enregistrer depuis la page Bender uniquement.')

    @router.get('')
    def list_poses():
        with connect() as db:
            rows = db.execute('SELECT * FROM creations ORDER BY kind,name').fetchall()
        return {'items': [result(row) for row in rows]}

    @router.post('', status_code=201)
    def create(pose: PoseSave, request: Request):
        origin_check(request)
        identifier = uuid.uuid4().hex
        try:
            with connect() as db:
                if db.execute('SELECT COUNT(*) FROM creations').fetchone()[0] >= 500:
                    raise HTTPException(409, 'Bibliothèque pleine (500 créations).')
                db.execute("INSERT INTO creations VALUES (?,?,?,?,1,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                           (identifier, pose.definition.kind, pose.name, pose.definition.model_dump_json()))
                row = db.execute('SELECT * FROM creations WHERE id=?', (identifier,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, 'Ce nom existe déjà. Choisis un autre nom pour la copie.') from exc
        return result(row)

    @router.put('/{identifier}')
    def update(identifier: str, pose: PoseSave, request: Request):
        origin_check(request)
        try:
            with connect() as db:
                current = db.execute('SELECT kind,revision FROM creations WHERE id=?', (identifier,)).fetchone()
                if not current: raise HTTPException(404, 'Création introuvable.')
                if current[0] != pose.definition.kind: raise HTTPException(422, 'Le type de création doit rester identique.')
                if pose.revision != current[1]: raise HTTPException(409, 'Cette création a changé dans une autre page. Recharge-la ou enregistre une copie.')
                updated = db.execute("UPDATE creations SET name=?,definition=?,revision=revision+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND revision=?",
                           (pose.name, pose.definition.model_dump_json(), identifier, pose.revision))
                if updated.rowcount != 1: raise HTTPException(409, 'La création vient de changer. Recharge-la avant de modifier.')
                row = db.execute('SELECT * FROM creations WHERE id=?', (identifier,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, 'Ce nom est utilisé par une autre création.') from exc
        return result(row)

    return router
