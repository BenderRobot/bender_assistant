"""Public build identity, fixed for the lifetime of the server process."""
import os
import re

UI_VERSION = 'atelier-gauche-20261024'
_candidate = os.environ.get('BENDER_REVISION', '')
REVISION = _candidate if re.fullmatch(r'[0-9a-f]{40}', _candidate) else None


def build_info():
    return {'revision': REVISION, 'ui_version': UI_VERSION}
