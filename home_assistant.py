# Stubs pour l'intégration future avec Home Assistant via l'API REST ou WebSockets

def turn_on_device(device_name: str, room: str) -> str:
    """
    Allume un appareil dans une pièce spécifique.
    """
    cmd = f"Action: Allumer {device_name} dans {room}"
    print(f"🏠 [HOME ASSISTANT] {cmd}")
    # TODO: Logique API Home Assistant ici
    return f"L'appareil {device_name} a été allumé dans {room}."

def turn_off_device(device_name: str, room: str) -> str:
    """
    Éteint un appareil dans une pièce spécifique.
    """
    cmd = f"Action: Éteindre {device_name} dans {room}"
    print(f"🏠 [HOME ASSISTANT] {cmd}")
    return f"L'appareil {device_name} a été éteint dans {room}."

def get_weather(location: str) -> str:
    """
    Récupère la météo pour un endroit donné.
    """
    cmd = f"Action: Obtenir météo pour {location}"
    print(f"☁️ [WEATHER API] {cmd}")
    return f"Il fait beau à {location} aujourd'hui."
