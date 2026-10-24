"""Check the running process and UI, rather than accepting any HTTP 200."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_info import UI_VERSION


def verify(base='http://127.0.0.1:8000', expected_revision=None):
    def read(path):
        with urlopen(base + path, timeout=4) as response:
            return response.read().decode('utf-8')

    version = json.loads(read('/api/system/version'))
    if version.get('ui_version') != UI_VERSION:
        raise ValueError('Interface servie incorrecte : ' + str(version.get('ui_version')))
    if expected_revision and version.get('revision') != expected_revision:
        raise ValueError('Revision servie differente du commit deploye : ' + str(version.get('revision')))
    paths = json.loads(read('/openapi.json'))['paths']
    for path in ('/api/media/{identifier}/reference', '/api/bulletins', '/api/voice/live-settings'):
        if path not in paths:
            raise ValueError('Application obsolete ; route absente : ' + path)
    if '/api/bulletins/play' not in read('/static/bulletins.js'):
        raise ValueError('Interface des bulletins absente')
    voice = json.loads(read('/api/voice/status'))
    if voice.get('cloud_integration') != 'sdk-with-timestamps-v1' or not voice.get('cloud_sdk_installed'):
        raise ValueError('SDK ElevenLabs absent ; verifier installation et redemarrage du service')
    if voice.get('cloud_enabled'):
        if not voice.get('cloud_key_configured'):
            raise ValueError('ElevenLabs active mais cle API absente du service ; verifier .env.elevenlabs et redemarrer bender.service')
        if not voice.get('cloud_voice_id'):
            raise ValueError('ElevenLabs active mais Voice ID absent ; choisir la voix dans l atelier')
    page = read('/')
    for marker in ('id="actualVoiceName"', '/static/voice-status.js', 'class="workspace-sidebar"', 'id="deploymentVersion"'):
        if marker not in page:
            raise ValueError('Atelier incomplet ; element absent : ' + marker)
    if 'BenderVoiceStatus' not in read('/static/voice-status.js'):
        raise ValueError('Affichage du moteur reel absent')
    return version


if __name__ == '__main__':
    try:
        version = verify(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000',
                         sys.argv[2] if len(sys.argv) > 2 else None)
    except Exception as error:
        raise SystemExit('Verification du deploiement echouee : ' + str(error))
    print('Version active verifiee :', version['ui_version'], version.get('revision'))
