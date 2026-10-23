import os
import asyncio
import threading
from pathlib import Path
from typing import Literal
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
load_dotenv()
from voice_api import router as voice_router, get_voice

brain_lock = threading.Lock()

def process_command(message, image_bytes=None):
    with brain_lock:
        from brain import process_command as process
        return process(message, image_bytes=image_bytes)
from memory import init_db, add_routine, get_routines, delete_routine

app = FastAPI(title="BenderV2 Web API")
ROOT = Path(__file__).resolve().parent
app.include_router(voice_router)
from hardware_api import build_hardware_router, require_control
app.include_router(build_hardware_router(process_command))
from brain_api import build_brain_router
app.include_router(build_brain_router())
from bender_brain import BrainError
from roadmap_api import build_roadmap_router
app.include_router(build_roadmap_router())
from bench_api import build_bench_router
app.include_router(build_bench_router())
from pose_api import build_pose_router
app.include_router(build_pose_router())
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
templates = Jinja2Templates(directory=str(ROOT / 'templates'))

# On s'assure que la DB existe au démarrage
init_db()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal['auto', 'local', 'cloud', 'cache'] = 'auto'
    mood: str = 'neutral'
    allow_quote: bool = False
    speech: bool = True

class RoutineRequest(BaseModel):
    name: str
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    """Sert l'interface web (chat)."""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get('/face', response_class=HTMLResponse)
async def serve_face(request: Request):
    return templates.TemplateResponse(request=request, name='index.html')

@app.get('/roadmap', response_class=HTMLResponse)
async def serve_roadmap(request: Request):
    return templates.TemplateResponse(request=request, name='roadmap.html')

@app.get('/kanban', response_class=HTMLResponse)
async def serve_kanban(request: Request):
    return templates.TemplateResponse(request=request, name='kanban.html')

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

@app.post("/api/chat", dependencies=[Depends(require_control)])
async def chat_endpoint(req: ChatRequest):
    """Endpoint API appelé par l'interface web pour parler à Bender."""
    try:
        user_message = req.message
        if not user_message:
            return {"error": "Message vide"}
            
        # Appel à notre intelligence existante
        response_text = await asyncio.to_thread(process_command, user_message)
        
        result = {"response": response_text}
        if req.speech:
            topic = 'news' if any(w in user_message.casefold() for w in ('actualité', 'actualite', 'news', 'nouvelles du jour')) else ''
            try:
                result['speech'] = await asyncio.to_thread(get_voice().prepare, response_text, req.mode,
                                                          req.mood, user_message, topic, req.allow_quote)
            except Exception:
                result['speech_error'] = 'Voix indisponible ; la réponse texte reste accessible'
        return result
    except BrainError as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "Cerveau GPT indisponible ; consulter son onglet et vérifier la connexion Internet. Le test voix seul reste disponible."}

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv('BENDER_HOST', '127.0.0.1'), port=int(os.getenv('BENDER_PORT', '8000')))
