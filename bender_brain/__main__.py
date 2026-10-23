"""Run on the host: python -m bender_brain login [--no-browser]."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from urllib.parse import urlsplit, parse_qs
import webbrowser

from dotenv import load_dotenv
from . import BrainError
from .auth import Auth


def login(auth, port=1455, no_browser=False, account=None, new=False):
    outcome = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log the callback query or authorization code.

        def do_GET(self):
            path = urlsplit(self.path)
            if path.path != '/auth/callback':
                self.send_error(404); return
            values = parse_qs(path.query, keep_blank_values=True)
            if any(len(v) != 1 for v in values.values()):
                self.send_error(400); return
            try:
                outcome['status'] = auth.complete(attempt, {k: v[0] for k, v in values.items()})
                message = 'Connexion enregistrée. Retourne à l’atelier Bender et actualise le statut du cerveau.'
                code = 200
            except BrainError as exc:
                message = str(exc); code = 400
                # Ignore mismatched state so an unsolicited local request cannot cancel login.
                if attempt.consumed:
                    outcome['error'] = message
            body = ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Bender · ChatGPT</title><p>' + message + '</p></html>').encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

    try:
        server = HTTPServer(('127.0.0.1', port), Callback)
    except OSError as exc:
        raise BrainError(f'Port de connexion {port} occupé ; fermer l’autre connexion ou choisir --port 1456 et adapter le tunnel SSH.') from exc
    with server:
        server.timeout = 1
        attempt = auth.begin(port, selected=account, new=new)
        url = attempt.url()
        print('Continuer avec ChatGPT / Continue with ChatGPT', flush=True)
        print('Ouvre ce lien dans ton navigateur et autorise Bender Jarvis :\n' + url, flush=True)
        print('Attente de ta connexion (10 minutes). Ctrl+C pour annuler.', flush=True)
        if not no_browser:
            webbrowser.open(url)
        deadline = time.monotonic() + 600
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
    if not outcome:
        raise BrainError('Délai de connexion dépassé ; relancer la connexion.')
    if 'error' in outcome:
        raise BrainError(outcome['error'])
    print(outcome['status']['message'])
    if not outcome['status']['authorized']:
        raise BrainError('Connexion établie sans permission d’utiliser le forfait. Vérifier les autorisations ChatGPT puis reconnecter.')


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='Compte ChatGPT du cerveau Bender, sans clé API payante.')
    sub = parser.add_subparsers(dest='command', required=True)
    signin = sub.add_parser('login')
    signin.add_argument('--no-browser', action='store_true')
    signin.add_argument('--port', type=int, default=1455)
    signin.add_argument('--account', help='Identifiant affiché par status pour réautoriser un compte enregistré')
    signin.add_argument('--new-account', action='store_true')
    sub.add_parser('status')
    sub.add_parser('logout')
    args = parser.parse_args()
    auth = Auth()
    try:
        if args.command == 'login':
            login(auth, args.port, args.no_browser, args.account, args.new_account)
        elif args.command == 'logout':
            revoked = auth.logout()
            print('Session déconnectée.' if revoked else 'Jetons effacés localement ; révocation distante non confirmée. Vérifier les applications connectées dans ChatGPT.')
        else:
            print(json.dumps(auth.status(private=True), ensure_ascii=False, indent=2))
    except BrainError as exc:
        parser.exit(1, str(exc) + '\n')
    except KeyboardInterrupt:
        parser.exit(1, 'Connexion annulée.\n')


if __name__ == '__main__':
    main()
