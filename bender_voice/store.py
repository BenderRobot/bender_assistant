import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root)
        for name in ('cache', 'library', 'references', 'models'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'voice.sqlite3'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS budget(day TEXT PRIMARY KEY, characters INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS played(id TEXT PRIMARY KEY, at REAL NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, characters, limit, monthly_limit=None):
        """Réserve avant l'appel : un échec réseau peut quand même être facturé."""
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT characters FROM budget WHERE day=?', (day,)).fetchone()
            used = row[0] if row else 0
            monthly = db.execute('SELECT COALESCE(SUM(characters),0) FROM budget WHERE substr(day,1,7)=?', (day[:7],)).fetchone()[0]
            if used + characters > limit or (monthly_limit is not None and monthly + characters > monthly_limit):
                return False
            db.execute('INSERT OR REPLACE INTO budget VALUES (?,?)', (day, used + characters))
            return True

    def usage(self):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            row = db.execute('SELECT characters FROM budget WHERE day=?', (day,)).fetchone()
            monthly = db.execute('SELECT COALESCE(SUM(characters),0) FROM budget WHERE substr(day,1,7)=?', (day[:7],)).fetchone()[0]
        return {'day_utc': day, 'characters_reserved': row[0] if row else 0, 'month_characters_reserved': monthly}

    def last_played(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT at FROM played WHERE id=?', (identifier,)).fetchone()
        return row[0] if row else 0

    def mark_played(self, identifier):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO played VALUES (?,?)', (identifier, time.time()))

    def library(self):
        path = self.root / 'library' / 'catalog.json'
        if not path.exists():
            return []
        entries = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(entries, list):
            raise ValueError('Le catalogue doit être une liste')
        return entries
