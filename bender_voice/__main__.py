import argparse
import json
import os
import subprocess
from pathlib import Path

from .config import inside, load_config
from .providers import VoiceUnavailable
from .service import VoiceService


def play(bundle, service):
    """Lecture sur le Dell. La page web gère séparément le visage synchronisé."""
    for segment in bundle['segments']:
        path = service.asset(segment['id'], 'wav')
        subprocess.run(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'error', str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description='Voix hybride Bender')
    parser.add_argument('--config')
    sub = parser.add_subparsers(dest='command', required=True)
    say = sub.add_parser('say');say.add_argument('text');say.add_argument('--mode', choices=['auto', 'local', 'cloud', 'cache'], default='auto')
    say.add_argument('--mood', default='neutral');say.add_argument('--context', default='');say.add_argument('--topic', default='')
    say.add_argument('--quotes', action='store_true');say.add_argument('--play', action='store_true')
    register = sub.add_parser('import');register.add_argument('audio', type=Path);register.add_argument('--id', required=True)
    register.add_argument('--text', required=True);register.add_argument('--type', choices=['basic', 'quote'], default='quote')
    register.add_argument('--trigger', action='append', default=[]);register.add_argument('--mood');register.add_argument('--timeline', type=Path)
    register.add_argument('--eyes', default='normal')
    sub.add_parser('status')
    sub.add_parser('control-token')
    download = sub.add_parser('download-models');download.add_argument('engine', choices=['chatterbox', 'allosaurus', 'vosk'])
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    config = load_config(args.config)
    service = VoiceService(config)
    if args.command == 'say':
        result = service.prepare(args.text, args.mode, args.mood, args.context, args.topic, args.quotes)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.play:
            play(result, service)
    elif args.command == 'import':
        result = service.register(args.audio, args.id, args.text, args.type, args.trigger, args.mood, args.timeline, args.eyes)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == 'status':
        print(json.dumps({'usage': service.store.usage(), 'library_entries': len(service.store.library()),
                          'cloud_enabled': config.get('elevenlabs', {}).get('enabled', False)}, indent=2))
    elif args.command == 'control-token':
        from .hardware import Hardware
        print(Hardware(config).control_token())
    elif args.engine == 'vosk':
        from .vosk_setup import download_vosk
        download_vosk(config)
    elif args.engine == 'chatterbox':
        from huggingface_hub import snapshot_download
        directory = inside(config['data_dir'], config.get('chatterbox', {}).get('model_dir', 'models/chatterbox'))
        snapshot_download('ResembleAI/chatterbox', local_dir=directory,
                          allow_patterns=['ve.pt', 't3_mtl23ls_v2.safetensors', 's3gen.pt',
                                          'grapheme_mtl_merged_expanded_v1.json', 'conds.pt', 'Cangjie5_TC.json'])
        print('Modèles Chatterbox téléchargés ; référence française à placer dans references/neutre.wav')
    else:
        from allosaurus.bin.download_model import download_model
        directory = inside(config['data_dir'], config.get('lipsync', {}).get('allosaurus_model_dir', 'models/allosaurus'))
        directory.mkdir(parents=True, exist_ok=True)
        download_model('uni2005', alt_model_path=directory)
        print('Modèle phonétique téléchargé ; activer lipsync.engine=allosaurus dans la configuration')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, VoiceUnavailable, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
