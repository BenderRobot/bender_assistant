"""Package the six reference recordings separately from Git (standard library only)."""
import argparse
import json
import shutil
import tarfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_dir():
        return False
    destination.mkdir(parents=True, exist_ok=True)
    tracks = json.loads((source / 'phonemes-tracks.json').read_text(encoding='utf-8-sig'))
    names = [('extrait-1', '1 · Au bar'), ('extrait-2', '2 · Référence bouche'),
             ('extrait-3', '3 · Expressions / Ouaiiii'), ('extrait-4', '4 · Noël'),
             ('extrait-5', '5 · Fauteuil'), ('replique-bender', 'Un déguisement ringard…')]
    visual = {'extrait-4': 'calage-noel.json', 'extrait-5': 'calage-fauteuil.json', 'replique-bender': 'replique-calage.json'}
    catalog = []
    for identifier, title in names:
        audio = source / f'{identifier}.wav'
        if not audio.is_file():
            continue
        with wave.open(str(audio)) as wav:
            duration = wav.getnframes() / wav.getframerate()
        shutil.copy2(audio, destination / audio.name)
        entry = {'id': identifier, 'title': title, 'audio': audio.name, 'duration': duration, 'methods': {}}
        candidates = {'phonemes': tracks.get(audio.name)}
        if identifier in visual:
            candidates['visual'] = json.loads((source / visual[identifier]).read_text(encoding='utf-8-sig'))
        for method, original in candidates.items():
            if not original or not original.get('cues'):
                continue
            cues = [dict(cue) for cue in original['cues'] if 0 <= cue.get('t', -1) <= duration and isinstance(cue.get('pose'), int) and 0 <= cue['pose'] <= 11]
            cues.sort(key=lambda cue: cue['t'])
            if not cues: continue
            filename = f'{identifier}-{method}.json'
            timeline = {'duration': duration, 'cues': cues, 'warnings': [
                'Calage visuel manuel provisoire.' if method == 'visual' else 'Phonèmes estimés sur cet extrait ; reconnaissance expérimentale, avec secours acoustique.'
            ]}
            (destination / filename).write_text(json.dumps(timeline, ensure_ascii=False), encoding='utf-8')
            entry['methods'][method] = filename
        catalog.append(entry)
    (destination / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'banc_essai')
    parser.add_argument('--destination', type=Path, default=ROOT / 'data' / 'reference_samples')
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
    catalog_path = args.destination / 'catalog.json'
    if not catalog_path.is_file():
        print('Pas de samples locaux à transférer ; les enregistrements Debian existants seront conservés.')
        return
    entries = json.loads(catalog_path.read_text(encoding='utf-8'))
    if args.archive:
        allowed = {'catalog.json'}
        for entry in entries:
            allowed.add(entry['audio']); allowed.update(entry['methods'].values())
        with tarfile.open(args.archive, 'w:gz') as archive:
            for name in sorted(allowed):
                if Path(name).name != name or Path(name).suffix not in ('.wav', '.json'):
                    raise ValueError('Nom de sample invalide')
                archive.add(args.destination / name, arcname=name, recursive=False)
    print(f'{len(entries)} enregistrements de référence prêts, conservés hors Git.')


if __name__ == '__main__':
    main()
