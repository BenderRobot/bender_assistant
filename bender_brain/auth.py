"""Official SIWC OAuth with PKCE, OIDC validation and rotating refresh tokens.

Protocol: https://developers.openai.com/siwc/token-sharing-open-source/sign-in
No ChatGPT browser cookies, Codex credentials or paid API-key fallback are used.
"""
import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.parse import urlencode
import uuid

import jwt
import requests

from . import BrainError

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
REVOKE = ISSUER + '/api/accounts/oauth/revoke'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
DIRECT_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + DIRECT_SCOPE
_mutex = threading.RLock()


class AuthRejected(BrainError):
    """The server rejected credentials rather than a temporary network outage."""


def data_directory():
    return Path(os.getenv('BENDER_BRAIN_DATA', Path(__file__).resolve().parents[1] / 'data' / 'brain'))


def account_id(client_id):
    return hashlib.sha256(client_id.encode()).hexdigest()[:16]


@dataclass
class Attempt:
    redirect_uri: str
    client_id: str
    host_id: str
    subject: str = ''
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    created_at: float = field(default_factory=time.time)
    consumed: bool = False

    def url(self):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b'=').decode()
        params = dict(client_id=self.client_id, ext_agent_host_id=self.host_id,
                      response_type='code', redirect_uri=self.redirect_uri, scope=SCOPES,
                      resource=RESOURCE, state=self.state, nonce=self.nonce,
                      code_challenge_method='S256', code_challenge=challenge)
        if self.client_id == 'dynamic_agent_client':
            params['agent_name_hint'] = 'Bender Jarvis'
        return AUTHORIZE + '?' + urlencode(params)


class Auth:
    def __init__(self, directory=None, http=None):
        self.directory = Path(directory) if directory is not None else data_directory()
        self.path = self.directory / 'chatgpt.json'
        self.http = http or requests.Session()
        self.jwks = jwt.PyJWKClient(JWKS, timeout=15)

    @contextmanager
    def locked(self):
        """Serialize CLI/server and threads, including the entire refresh exchange."""
        with _mutex:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name != 'nt':
                self.directory.chmod(0o700)
            fd = os.open(self.directory / '.auth.lock', os.O_RDWR | os.O_CREAT, 0o600)
            with os.fdopen(fd, 'r+b') as lock:
                if os.name == 'nt':
                    import msvcrt
                    if not lock.read(1):
                        lock.write(b'0'); lock.flush()
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    lock.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self):
        if not self.path.exists():
            return {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'active': '', 'accounts': {}}
        try:
            doc = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(doc['accounts'], dict) or not doc['host_id'].startswith('urn:uuid:'):
                raise ValueError()
            return doc
        except (ValueError, KeyError, TypeError) as exc:
            raise BrainError('Configuration ChatGPT illisible ; restaurer data/brain/chatgpt.json depuis une sauvegarde.') from exc

    def _write(self, doc):
        fd, name = tempfile.mkstemp(prefix='.chatgpt-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(doc, output, ensure_ascii=False)
                output.flush(); os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def begin(self, port=1455, selected=None, new=False):
        if not 1024 <= port <= 65535:
            raise BrainError('Choisir un port de connexion entre 1024 et 65535.')
        with self.locked():
            doc = self._read()
            selected = selected if selected is not None else doc['active']
            if selected and selected not in doc['accounts']:
                raise BrainError('Compte inconnu ; utiliser status pour voir les comptes enregistrés.')
            previous = {} if new else doc['accounts'].get(selected, {})
            self._write(doc)  # Persist the host ID before the first authorization.
        return Attempt(f'http://127.0.0.1:{port}/auth/callback',
                       previous.get('client_id', 'dynamic_agent_client'), doc['host_id'], previous.get('subject', ''))

    def _post(self, endpoint, payload):
        try:
            response = self.http.post(endpoint, data=payload, timeout=(10, 30), allow_redirects=False)
            with response:
                if response.status_code in (400, 401, 403):
                    raise AuthRejected('Connexion ChatGPT expirée ou refusée ; relancer CONNECTER_CHATGPT.ps1.')
                if response.status_code != 200:
                    raise BrainError('Service de connexion ChatGPT temporairement indisponible ; réessayer plus tard.')
                data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (requests.RequestException, ValueError) as exc:
            raise BrainError('Serveur de connexion ChatGPT inaccessible ; vérifier Internet puis réessayer.') from exc

    def _validate_id(self, token, client_id, nonce=None):
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=['RS256'], audience=client_id,
                                issuer=ISSUER, options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
            if not claims.get('sub') or (nonce is not None and not hmac.compare_digest(str(claims.get('nonce', '')).encode(), nonce.encode())):
                raise ValueError()
            return claims
        except Exception as exc:
            raise BrainError('Identité ChatGPT non vérifiée ; aucune nouvelle session enregistrée.') from exc

    @staticmethod
    def _tokens(data, previous=None):
        previous = previous or {}
        if not isinstance(data.get('access_token'), str) or not data['access_token'] or str(data.get('token_type', '')).lower() != 'bearer':
            raise BrainError('Réponse de connexion ChatGPT incomplète ; recommencer la connexion.')
        try:
            expires = float(data['expires_in'])
            if not 0 < expires < 366 * 86400:
                raise ValueError()
        except (KeyError, TypeError, ValueError) as exc:
            raise BrainError('Expiration ChatGPT invalide ; recommencer la connexion.') from exc
        scope = data.get('scope')
        scopes = scope.split() if isinstance(scope, str) else previous.get('scopes', [])
        return dict(access_token=data['access_token'], refresh_token=data.get('refresh_token', previous.get('refresh_token', '')),
                    id_token=data.get('id_token', previous.get('id_token', '')), token_type='Bearer',
                    scopes=scopes, expires_at=time.time() + expires, saved_at=time.time())

    def complete(self, attempt, params):
        if attempt.consumed or time.time() - attempt.created_at > 600:
            raise BrainError('Tentative expirée ; relancer la connexion.')
        if not hmac.compare_digest(str(params.get('state', '')).encode(), attempt.state.encode()):
            raise BrainError('Retour de connexion non reconnu ; aucune session modifiée.')
        attempt.consumed = True
        if params.get('error'):
            raise BrainError('Autorisation ChatGPT refusée ou annulée ; aucune session modifiée.')
        issued = params.get('client_id', '')
        if attempt.client_id == 'dynamic_agent_client':
            if not issued or issued == 'dynamic_agent_client':
                raise BrainError('Identifiant de connexion absent du retour ChatGPT.')
        else:
            if issued and issued != attempt.client_id:
                raise BrainError('Le compte retourné ne correspond pas à cette connexion.')
            issued = attempt.client_id
        if not params.get('code'):
            raise BrainError('Code de connexion ChatGPT absent.')
        data = self._post(TOKEN, dict(grant_type='authorization_code', client_id=issued,
                          code=params['code'], code_verifier=attempt.verifier, redirect_uri=attempt.redirect_uri, resource=RESOURCE))
        claims = self._validate_id(data.get('id_token', ''), issued, attempt.nonce)
        if attempt.subject and claims['sub'] != attempt.subject:
            raise BrainError('Autre compte retourné ; utiliser --new-account pour l’enregistrer séparément.')
        credentials = self._tokens(data)
        record = dict(client_id=issued, issuer=ISSUER, subject=claims['sub'], email=claims.get('email', ''), **credentials)
        with self.locked():
            doc = self._read()
            if doc['host_id'] != attempt.host_id:
                raise BrainError('Hôte de connexion modifié ; recommencer.')
            identifier = account_id(issued)
            previous = doc['accounts'].get(identifier, {})
            if previous and previous['subject'] != claims['sub']:
                raise BrainError('Identité différente pour ce compte ; session précédente conservée.')
            record['model'] = previous.get('model', '')
            doc['accounts'][identifier] = record
            doc['active'] = identifier
            self._write(doc)
        return self.status(private=True)

    def status(self, private=False):
        with self.locked():
            doc = self._read()
            account = doc['accounts'].get(doc['active'], {})
        connected = bool(account.get('access_token') or account.get('refresh_token'))
        allowed = connected and DIRECT_SCOPE in account.get('scopes', [])
        result = dict(provider='chatgpt', connected=connected, authorized=allowed, model=account.get('model', ''),
                      message='ChatGPT connecté.' if allowed else 'Permission d’utilisation du forfait ChatGPT absente.' if connected else 'Connexion ChatGPT à effectuer depuis CONNECTER_CHATGPT.ps1.')
        if private:
            result['active_account'] = doc['active']
            result['accounts'] = [dict(id=key, label=f"{value.get('email') or 'Compte ChatGPT'} · {key[:6]}",
                                        signed_in=bool(value.get('access_token') or value.get('refresh_token')))
                                  for key, value in doc['accounts'].items()]
        return result

    def credential(self):
        with self.locked():
            doc = self._read()
            identifier = doc['active']
            account = doc['accounts'].get(identifier, {})
            if not account.get('access_token'):
                raise BrainError('ChatGPT non connecté ; lancer CONNECTER_CHATGPT.ps1 après la mise à jour du Debian.')
            if DIRECT_SCOPE not in account.get('scopes', []):
                raise BrainError('Ce compte n’a pas autorisé l’utilisation du forfait ChatGPT ; refaire la connexion et vérifier son éligibilité.')
            if account.get('expires_at', 0) < time.time() + 60:
                if not account.get('refresh_token'):
                    raise BrainError('Session ChatGPT expirée ; relancer CONNECTER_CHATGPT.ps1.')
                try:
                    data = self._post(TOKEN, dict(grant_type='refresh_token', client_id=account['client_id'],
                                      refresh_token=account['refresh_token'], resource=RESOURCE))
                except AuthRejected:
                    account.pop('access_token', None); account.pop('refresh_token', None); account.pop('id_token', None)
                    self._write(doc)
                    raise
                try:
                    if data.get('id_token'):
                        claims = self._validate_id(data['id_token'], account['client_id'])
                        if claims['sub'] != account['subject']:
                            raise BrainError('Identité différente lors du renouvellement ; reconnecter ChatGPT.')
                    account.update(self._tokens(data, account))
                except BrainError:
                    # A successful exchange rotated the token, but could not be validated.
                    account.pop('access_token', None); account.pop('refresh_token', None); account.pop('id_token', None)
                    self._write(doc)
                    raise
                self._write(doc)
                if DIRECT_SCOPE not in account.get('scopes', []):
                    raise BrainError('Permission ChatGPT retirée ; reconnecter le compte.')
            return identifier, dict(account)

    def select_account(self, identifier):
        with self.locked():
            doc = self._read()
            if identifier not in doc['accounts']:
                raise BrainError('Compte ChatGPT inconnu.')
            doc['active'] = identifier
            self._write(doc)

    def select_model(self, identifier, slug):
        with self.locked():
            doc = self._read()
            if doc['active'] != identifier:
                raise BrainError('Compte changé pendant le chargement ; actualiser les modèles.')
            doc['accounts'][identifier]['model'] = slug
            self._write(doc)

    def logout(self):
        revoked = True
        with self.locked():
            doc = self._read()
            account = doc['accounts'].get(doc['active'], {})
            if account.get('refresh_token'):
                try:
                    with self.http.post(REVOKE, data=dict(token=account['refresh_token'], token_type_hint='refresh_token',
                                                        client_id=account['client_id']), timeout=(10, 30), allow_redirects=False) as response:
                        revoked = response.status_code == 200
                except requests.RequestException:
                    revoked = False
            for name in ('access_token', 'refresh_token', 'id_token'):
                account.pop(name, None)
            self._write(doc)
        return revoked
