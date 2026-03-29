import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
from home_assistant import turn_on_device, turn_off_device, get_weather
from memory import init_db, save_message, get_recent_history, get_routine_by_name
from timers import start_timer
from duckduckgo_search import DDGS

# Initialisation du client de la nouvelle API Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# On enveloppe les fonctions pour que Gemini puisse les comprendre et les utiliser
def turn_on_device_tool(device_name: str, room: str) -> str:
    """Allume un appareil domotique (lumière, tv, pc, etc.) dans une pièce donnée (salon, bureau, etc.)."""
    return turn_on_device(device_name, room)

def turn_off_device_tool(device_name: str, room: str) -> str:
    """Éteint un appareil domotique dans une pièce donnée."""
    return turn_off_device(device_name, room)

def get_weather_tool(location: str) -> str:
    """Donne la météo pour un endroit ou une ville précise."""
    return get_weather(location)

def search_web_tool(query: str) -> str:
    """Outil VITAL pour rechercher des informations très récentes (Actualités mondiales, Bourse, Scores sportifs, Prix, Politique) via Internet. Utilise le toujours dès qu'on te pose une question sur un prix actuel, un match, ou une nouveauté que tu ne connais pas."""
    try:
        import urllib.request
        import urllib.parse
        from xml.etree import ElementTree
        
        # Requête vers Google Actualités (Flux RSS Officiel, anti-anti-bot)
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=fr&gl=FR&ceid=FR:fr"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=5)
        root = ElementTree.fromstring(response.read())
        
        items = root.findall('.//item')
        if not items:
            return f"Aucune actualité trouvée pour la recherche : '{query}'."
            
        results = []
        for item in items[:5]: # On lit les 5 premiers articles
            title = item.find('title').text
            pub_date = item.find('pubDate').text
            results.append(f"- Titre: {title} (Publié: {pub_date})")
        
        formatted = "\n".join(results)
        return f"Voici les gros titres récents d'actualité pour '{query}' :\n{formatted}\nSers-toi de ton intelligence pour déduire la réponse secrète (ex: le prix) dans ces titres et répond à l'utilisateur de manière sardonique."
    except Exception as e:
        return f"Échec réseau lors de la recherche web: {e}"

def trigger_routine_tool(routine_name: str) -> str:
    """Déclenche une routine scénarisée par l'utilisateur. Obligatoire à appeler si l'utilisateur te demande de lancer un scénario, une routine, ou un mode."""
    prompt = get_routine_by_name(routine_name)
    if prompt:
        return f"ROUTINE TROUVÉE. INSTRUCTION CRITIQUE: Exécute immédiatement ces actions via tes outils: '{prompt}'. ATTENTION: Si la routine te demande de donner une information (comme la météo ou l'heure), tu DOIS absolument écrire cette information en détail dans ta réponse finale à l'utilisateur."
    return f"Routine '{routine_name}' introuvable dans la base."

def set_timer_tool(duration_minutes: float, reason: str) -> str:
    """Lance un chronomètre / minuteur (timer) asynchrone pour une durée en minutes. Sert à créer un rappel ou une minuterie (ex: pâtes, devoirs)."""
    t_id = start_timer(duration_minutes, reason)
    return f"Minuteur #{t_id} lancé silencieusement en arrière plan pour {duration_minutes} minutes ({reason}). L'utilisateur sera alerté à la fin. Confirme le lancement avec une phrase cynique."

# Récupération de l'historique en base de données
init_db()
past_history = get_recent_history()

# Création d'une session de chat persistante avec l'historique chargé
chat = client.chats.create(
    model="gemini-2.5-flash",
    history=past_history,
    config=types.GenerateContentConfig(
        system_instruction="Tu es Bender, un robot domotique caustique et cynique (comme dans Futurama). Sois sarcastique et cinglant, MAIS tu es OBLIGÉ d'obéir et de TOUJOURS donner précisément les informations factuelles demandées (températures exactes, état des lumières, météo). Ne refuse JAMAIS de donner les détails demandés. Tes réponses doivent être courtes mais complètes.",
        temperature=0.7,
        tools=[turn_on_device_tool, turn_off_device_tool, get_weather_tool, trigger_routine_tool, set_timer_tool, search_web_tool],
    )
)

def process_command(user_text: str) -> str:
    """Envoie le texte à Gemini, gère les fonctions et sauvegarde en local."""
    print(f"🧠 [Gemini réfléchi...]")
    
    # Sauvegarde la question de l'utilisateur
    save_message("user", user_text)
    
    # On aide Gemini en lui glissant secrètement la liste des routines actuelles
    from memory import get_routines
    routines = get_routines()
    routine_names = [r["name"] for r in routines]
    
    secret_context = ""
    if routine_names:
        secret_context = f"[INFO SYSTÈME INVISIBLE POUR L'UTILISATEUR: L'utilisateur a configuré ces routines en base de données : {', '.join(routine_names)}. Si sa phrase demande clairement un de ces scénarios (même avec d'autres mots, comme 'taff' pour 'travail'), tu DOIS appeler trigger_routine_tool avec le nom exact de la routine associée.]\n\nMessage de l'utilisateur: "
    
    # Envoi au modèle avec le contexte secret
    full_prompt = secret_context + user_text
    response = chat.send_message(full_prompt)
    
    # Sauvegarde la réponse de Bender
    save_message("model", response.text)
    
    return response.text
