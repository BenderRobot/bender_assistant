import os
import sys
from dotenv import load_dotenv
from audio import listen, speak, init_tts
from brain import process_command

def main():
    load_dotenv()
    if not os.environ.get("GEMINI_API_KEY"):
        print("Erreur: GEMINI_API_KEY manquante. Veuillez copier .env.example vers .env et y mettre votre clé.")
        sys.exit(1)

    print("🤖 Welcome to Bendervoice V2")
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
                speak(response_text, engine)
                
        except KeyboardInterrupt:
            speak("Arrêt forcé.", engine)
            break

if __name__ == "__main__":
    main()
