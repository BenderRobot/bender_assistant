"""Exact social phrases that do not need a remote reasoning request."""
import re
import unicodedata


def quick_reply(text):
    normalized = ''.join(letter for letter in unicodedata.normalize('NFD', text.casefold())
                         if not unicodedata.combining(letter))
    normalized = ' '.join(re.findall(r'\w+', normalized))
    if normalized in ('salut', 'salut bender', 'bonjour', 'bonjour bender', 'coucou', 'coucou bender'):
        return 'Salut Benjamin. Mes circuits sont prêts, malgré leurs protestations.'
    if normalized in ('bonsoir', 'bonsoir bender'):
        return 'Bonsoir Benjamin. Mes circuits sont prêts, ma patience est en option.'
    if normalized in ('merci', 'merci bender'):
        return 'De rien. Un robot aussi modeste que moi, ça ne court pas les rues.'
    if normalized in ('au revoir', 'au revoir bender', 'a bientot', 'a plus'):
        return 'À plus, Benjamin. Je garde mes circuits au chaud.'
    return None
