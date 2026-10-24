"""Short, reusable acknowledgements. Reading the catalogue never synthesizes."""
from .providers import VoiceUnavailable

PHRASES = ('Bonne question, je regarde ça.', 'Un instant, je réfléchis.')


def catalogue(voice):
    provider = voice.providers['elevenlabs']
    items = []
    missing = []
    # Do not take the synthesis lock: this is read while the real answer may
    # already be generating. An incomplete cache entry is simply not ready yet.
    for text in PHRASES:
        key = voice._key(text, provider, 'neutral')
        try:
            if not voice.asset(key, 'wav').is_file():raise FileNotFoundError()
            segment = voice._segment(key, 'elevenlabs', cached=True)
            if not 0 < segment['duration'] <= 10:raise ValueError('Invalid acknowledgement duration')
            items.append(segment)
        except (OSError, ValueError, KeyError):
            missing.append(text)
    return {'items': items, 'total': len(PHRASES), 'ready': len(items),
            'missing_characters': sum(len(text) for text in missing)}


def prepare(voice):
    # Called only by the explicit owner action, never during a conversation.
    with voice.lock:
        if not voice.config.get('elevenlabs', {}).get('enabled'):
            raise VoiceUnavailable('Activer ElevenLabs avant de préparer les phrases d’attente.')
        for text in PHRASES:
            voice._generate(text, 'neutral', voice.providers['elevenlabs'], [])
    return catalogue(voice)
