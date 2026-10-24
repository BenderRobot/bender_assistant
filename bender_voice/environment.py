"""Load private project settings without depending on the launch directory."""
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_environment(root=ROOT):
    # Explicit process variables win; the newly authorized key wins over .env.
    root = Path(root)
    load_dotenv(root / ".env.elevenlabs", override=False)
    load_dotenv(root / ".env", override=False)
