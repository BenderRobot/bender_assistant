import sqlite3
import json

DB_PATH = "bender_memory.db"

def init_db():
    """Initialise la base de données de mémoire."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_routine(name: str, prompt: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO routines (name, prompt) VALUES (?, ?)", (name, prompt))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

def get_routines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, prompt FROM routines")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "prompt": r[2]} for r in rows]

def get_routine_by_name(name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT prompt FROM routines WHERE name COLLATE NOCASE = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_routine(routine_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
    conn.commit()
    conn.close()

def save_message(role: str, content: str):
    """Sauvegarde un message dans la base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def get_recent_history(limit: int = 20):
    """Récupère les derniers messages pour le contexte Gemini."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # On récupère les messages, mais on doit les remettre dans l'ordre chronologique
    # On filtre sur 'user' et 'model' car l'API Gemini plante si on lui donne 'bot' ou 'system'
    cursor.execute("SELECT role, content FROM (SELECT * FROM messages WHERE role IN ('user', 'model') ORDER BY id DESC LIMIT ?) ORDER BY id ASC", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    # Formatage pour Gemini SDK
    history = []
    for role, content in rows:
        history.append({
            "role": role,
            "parts": [{"text": content}]
        })
    return history

# On initialise la BDD si elle n'existe pas
init_db()
