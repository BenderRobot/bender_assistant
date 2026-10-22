"""Entrée micro et sortie vocale hybride. Aucun shell construit avec le texte."""
import functools
import subprocess


@functools.lru_cache(maxsize=1)
def init_tts():
    from voice_api import get_voice
    return get_voice()


def speak(text, engine=None, **options):
    from bender_voice.__main__ import play
    service = engine or init_tts()
    print(f'Bender: {text}')
    try:
        bundle = service.prepare(text, **options)
        for warning in bundle['warnings']:
            print(f'Voix : {warning}')
        play(bundle, service)
        return bundle
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'Sortie vocale indisponible : {exc}')
        return None


def listen():
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("J'écoute…")
            recognizer.adjust_for_ambient_noise(source)
            recording = recognizer.listen(source, timeout=10, phrase_time_limit=30)
        text = recognizer.recognize_google(recording, language='fr-FR')
        print(f'Vous : {text}')
        return text
    except (AttributeError, OSError):
        return input('Commande au clavier : ')
    except (sr.UnknownValueError, sr.WaitTimeoutError):
        return None
    except sr.RequestError:
        print('Reconnaissance Google indisponible ; utiliser le clavier ou la page web')
        return None
