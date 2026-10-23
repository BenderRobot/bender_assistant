import sys
from dotenv import load_dotenv
from audio import listen, speak, init_tts

def main():
    load_dotenv()
    from bender_brain.auth import Auth
    if not Auth().status()['authorized']:
        print("Connecter le compte : .venv/bin/python -m bender_brain login")
        sys.exit(1)

    print("🤖 Welcome to Bendervoice V2")
    from brain import process_command
    engine = init_tts()
    speak("Je suis de retour. Tu veux quoi, l'organic ?", engine)
    
    while True:
        try:
            print("\n--- En attente (Parlez dans le micro) ---")
            text = listen()
            
            if text:
                if "quitter" in text.lower() or "exit" in text.lower():
                    speak("À plus dans le bus.", engine)
                    break
                
                # Envoi du texte au cerveau LLM
                response_text = process_command(text)
                topic = 'news' if any(w in text.casefold() for w in ('actualité', 'actualite', 'news', 'nouvelles du jour')) else ''
                speak(response_text, engine, context=text, topic=topic, allow_quote=True)
                
        except KeyboardInterrupt:
            speak("Arrêt forcé.", engine)
            break

if __name__ == "__main__":
    main()
