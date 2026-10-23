"""ChatGPT is Bender's brain; Vosk and speech synthesis remain independent."""
from brain_api import get_brain, brain_lock


def process_command(user_text: str, image_bytes: bytes | None = None) -> str:
    with brain_lock:
        return get_brain().respond(user_text, image_bytes=image_bytes)
