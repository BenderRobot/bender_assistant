import speech_recognition as sr
import pyttsx3

def init_tts():
    engine = pyttsx3.init()
    # On peut configurer la voix FR ici
    voices = engine.getProperty('voices')
    for voice in voices:
        if 'fr' in voice.languages or 'French' in voice.name:
            engine.setProperty('voice', voice.id)
            break
    return engine

def speak(text, engine=None):
    if engine is None:
        engine = init_tts()
    print(f"🤖 Bender: {text}")
    engine.say(text)
    engine.runAndWait()

def listen():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("🎤 J'écoute...")
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source)

        text = r.recognize_google(audio, language="fr-FR")
        print(f"👤 Vous: {text}")
        return text
    except AttributeError:
        # Pyaudio n'est pas installé
        print("⚠️ [Erreur Micro] PyAudio n'est pas installé.")
        text = input("👤 Tapez votre commande au clavier : ")
        return text
    except sr.UnknownValueError:
        print("Bender n'a pas compris l'audio.")
        return None
    except sr.RequestError as e:
        print(f"Erreur de service Speech Recognition; {e}")
        return None
