from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

EXTENSIONS = {'.wav','.mp3','.mp4','.m4a','.ogg','.flac','.webm','.mov','.mkv'}
MAX_FILE = 100 * 1024 * 1024
MAX_BATCH = 500 * 1024 * 1024


def valid_id(identifier):
    if not re.fullmatch(r'[a-f0-9]{64}', identifier):
        raise ValueError('Identifiant de sample invalide')
    return identifier


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


class Catalog:
    def __init__(self, root):
        self.root = Path(root)
        for directory in ('originals','derived','approved'):
            (self.root/directory).mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS samples (
                    id TEXT PRIMARY KEY, original_name TEXT NOT NULL, extension TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', created REAL NOT NULL, updated REAL NOT NULL,
                    error TEXT NOT NULL DEFAULT '', media TEXT NOT NULL DEFAULT '{}',
                    analysis TEXT NOT NULL DEFAULT '{}', approved TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root/'catalog.sqlite3',timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def original(self, identifier):
        row=self.get(identifier)
        return self.root/'originals'/(identifier+row['extension'])

    def derived(self, identifier):
        directory=self.root/'derived'/valid_id(identifier)
        directory.mkdir(parents=True,exist_ok=True)
        return directory

    def add(self, identifier, name, extension):
        valid_id(identifier)
        if extension not in EXTENSIONS or not name or len(name)>255:
            raise ValueError('Nom ou format du média invalide')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO samples(id,original_name,extension,created,updated) VALUES(?,?,?,?,?)',
                       (identifier,name,extension,time.time(),time.time()))

    @staticmethod
    def decode(row):
        result=dict(row)
        for key in ('media','analysis','approved'):result[key]=json.loads(result[key])
        return result

    def get(self,identifier):
        valid_id(identifier)
        with self.connect() as db:row=db.execute('SELECT * FROM samples WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('Sample introuvable')
        return self.decode(row)

    def list(self):
        with self.connect() as db:rows=db.execute('SELECT * FROM samples ORDER BY created DESC LIMIT 1000').fetchall()
        return [self.decode(row) for row in rows]

    def inventory(self):
        with self.connect() as db:rows=db.execute('SELECT id,extension FROM samples').fetchall()
        return [row['id'] for row in rows if (self.root/'originals'/(row['id']+row['extension'])).is_file()]

    def update(self, identifier, **values):
        if set(values)-{'state','error','media','analysis','approved'}:raise ValueError('Champ invalide')
        values={key:json.dumps(value,ensure_ascii=False) if key in ('media','analysis','approved') else value for key,value in values.items()}
        values['updated']=time.time()
        with self.connect() as db:
            db.execute('UPDATE samples SET '+','.join(key+'=?' for key in values)+' WHERE id=?',(*values.values(),valid_id(identifier)))

    def automatic(self, enabled=None):
        with self.connect() as db:
            if enabled is not None:
                db.execute("INSERT OR REPLACE INTO settings VALUES('automatic',?)",('1' if enabled else '0',))
            row=db.execute("SELECT value FROM settings WHERE key='automatic'").fetchone()
        return row is None or row['value']=='1'
