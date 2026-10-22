import time
import threading
import os
from memory import save_message

# Dictionnaire pour stocker les minuteurs actifs en mémoire RAM
active_timers = {}
timer_id_counter = 0

def _timer_callback(timer_id: int, reason: str):
    """Fonction appelée quand le minuteur arrive à zéro."""
    # Alerte vocale via le même moteur portable que les réponses.
    alert_text = f"Alerte minuteur organiques ! Il est temps pour : {reason}"
    # Éxecution en fond
    from audio import speak
    speak(alert_text)
    
    # 2. Sauvegarde un message système pour le chat web
    save_message("bot", f"⏰ Bip bip ! Minuteur terminé : {reason}")
    
    # 3. Supprime des minuteurs actifs
    if timer_id in active_timers:
        del active_timers[timer_id]

def start_timer(duration_minutes: float, reason: str) -> int:
    """Lance un chronomètre en arrière-plan et le stocke."""
    global timer_id_counter
    timer_id_counter += 1
    
    duration_seconds = duration_minutes * 60
    ends_at = time.time() + duration_seconds
    
    # Création du thread asynchrone qui attend
    t = threading.Timer(duration_seconds, _timer_callback, args=[timer_id_counter, reason])
    t.start()
    
    active_timers[timer_id_counter] = {
        "id": timer_id_counter,
        "reason": reason,
        "ends_at": ends_at
    }
    
    return timer_id_counter

def get_active_timers():
    """Retourne la liste des minuteurs en cours pour le widget web."""
    now = time.time()
    timers_list = []
    for t_id, t_info in active_timers.items():
        remaining = int(t_info["ends_at"] - now)
        if remaining > 0:
            timers_list.append({
                "id": t_id,
                "reason": t_info["reason"],
                "remaining_seconds": remaining
            })
    return timers_list
