import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from brain import process_command
from memory import init_db, add_routine, get_routines, delete_routine

app = FastAPI(title="BenderV2 Web API")
templates = Jinja2Templates(directory="templates")

# On s'assure que la DB existe au démarrage
init_db()

class ChatRequest(BaseModel):
    message: str

class RoutineRequest(BaseModel):
    name: str
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    """Sert l'interface web (chat)."""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/routines")
async def fetch_routines():
    """Récupère la liste des routines."""
    return get_routines()

@app.get("/api/history")
async def fetch_history():
    """Récupère tout l'historique pour mettre à jour le chat en direct."""
    import sqlite3
    from memory import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, role, content FROM messages ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2]} for r in rows]

@app.post("/api/routines")
async def create_routine(req: RoutineRequest):
    """Crée ou met à jour une routine."""
    success = add_routine(req.name, req.prompt)
    if success:
        return {"status": "ok"}
    return {"error": "Failed to add routine"}

@app.delete("/api/routines/{routine_id}")
async def remove_routine(routine_id: int):
    """Supprime une routine."""
    delete_routine(routine_id)
@app.delete("/api/timers/{timer_id}")
async def stop_timer(timer_id: int):
    # Facultatif pour plus tard
    return {"status": "ok"}

from timers import get_active_timers
@app.get("/api/timers")
async def fetch_timers():
    """Récupère les minuteurs actifs pour le widget web."""
    return get_active_timers()

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Endpoint API appelé par l'interface web pour parler à Bender."""
    try:
        user_message = req.message
        if not user_message:
            return {"error": "Message vide"}
            
        # Appel à notre intelligence existante
        response_text = process_command(user_message)
        
        return {"response": response_text}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("🚀 Démarrage du serveur Web Bender sur http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
