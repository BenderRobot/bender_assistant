"""Reversible housekeeping of source media; runtime assets are never moved."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

EXTENSIONS={'.wav','.mp3','.mp4','.m4a','.flac','.ogg','.webm','.mov','.mkv'}
VIDEO={'.mp4','.webm','.mov','.mkv'}


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
    return sha.hexdigest()


def plan(root,downloads=None):
    root=Path(root).resolve(strict=True);media=root/'02_VOIX_ET_ANIMATIONS'
    inbox=media/'a_importer'
    sources=[]
    for folder,recursive in [(inbox,True),(media/'montage_elevenlabs'/'extraits',True),
                             (media/'montage_elevenlabs',False)]:
        if folder.is_dir():
            sources.extend(path for path in (folder.rglob('*') if recursive else folder.iterdir())
                           if path.is_file() and not path.is_symlink() and path.suffix.lower() in EXTENSIONS)
    if downloads:
        sources.extend(path for path in Path(downloads).resolve(strict=True).iterdir()
                       if path.is_file() and not path.is_symlink() and path.suffix.lower() in EXTENSIONS
                       and path.name.lower().startswith('elevenlabs_') and 'bender' in path.name.lower())
    reserved={};moves=[]
    for source in sorted(set(sources),key=lambda p:(len(p.parts),str(p).casefold())):
        source=source.resolve(strict=True)
        category=('voix_elevenlabs' if source.name.lower().startswith('elevenlabs_') else
                  'videos_originales' if source.suffix.lower() in VIDEO else 'sons_originaux')
        target=(inbox/category/source.name).resolve();sha=digest(source)
        duplicate=False
        if target!=source and (target in reserved or target.exists()):
            previous=reserved.get(target) or digest(target)
            if previous==sha:
                duplicate=True
                target=(media/'_archives_rangement'/'doublons'/source.name).resolve()
            else:
                target=target.with_name(f'{target.stem}__{sha[:10]}{target.suffix}')
        if target==source:reserved[target]=sha;continue
        serial=1;candidate=target
        while candidate in reserved or candidate.exists():
            candidate=target.with_name(f'{target.stem}__{sha[:8]}_{serial}{target.suffix}');serial+=1
        target=candidate
        if not target.is_relative_to(media.resolve()):raise ValueError('Destination hors du dossier média')
        reserved[target]=sha
        moves.append(dict(source=str(source),destination=str(target),sha256=sha,duplicate=duplicate,done=False))
    return dict(root=str(root),allowed_sources=[str(media.resolve()),*([str(Path(downloads).resolve())] if downloads else [])],
                created=datetime.now().astimezone().isoformat(),moves=moves)


def write_inventory(root):
    media=Path(root).resolve()/'02_VOIX_ET_ANIMATIONS'
    rows=[]
    for path in sorted(media.rglob('*')):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in EXTENSIONS:
            if not path.resolve().is_relative_to(media.resolve()):raise ValueError('Média hors du dossier prévu')
            rows.append(dict(dossier=path.parent.relative_to(media).as_posix(),fichier=path.name,
                             octets=path.stat().st_size,sha256=digest(path)))
    with (media/'MEDIATHEQUE.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['dossier','fichier','octets','sha256'],delimiter=';')
        writer.writeheader();writer.writerows(rows)


def apply(plan_data,manifest):
    root=Path(plan_data['root']).resolve(strict=True)
    manifest=Path(manifest).resolve()
    if not manifest.is_relative_to(root):raise ValueError('Conserver le manifeste dans le projet')
    manifest.parent.mkdir(parents=True,exist_ok=True)
    def save():manifest.write_text(json.dumps(plan_data,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    for move in plan_data['moves']:
        source=Path(move['source']).resolve(strict=True);target=Path(move['destination']).resolve()
        if not any(source.is_relative_to(Path(allowed).resolve()) for allowed in plan_data['allowed_sources']):
            raise ValueError('Source hors des dossiers prévus')
        if not target.is_relative_to(root/'02_VOIX_ET_ANIMATIONS'):raise ValueError('Destination hors du dossier média')
        if target.exists() or digest(source)!=move['sha256']:raise ValueError('Le plan a changé ; relancer le rangement')
        target.parent.mkdir(parents=True,exist_ok=True)
        source.rename(target)
        move['done']=True;save()
        if digest(target)!=move['sha256']:raise ValueError('Empreinte incorrecte après déplacement')
    write_inventory(root)
    return plan_data


def restore(manifest):
    """Only reverse the exact verified paths from our manifest, without overwrite."""
    manifest=Path(manifest).resolve(strict=True)
    data=json.loads(manifest.read_text(encoding='utf-8'))
    root=Path(data['root']).resolve(strict=True)
    if not manifest.is_relative_to(root):raise ValueError('Manifeste hors du projet')
    for move in reversed(data['moves']):
        if not move['done']:continue
        source=Path(move['destination']).resolve(strict=True);target=Path(move['source']).resolve()
        if not source.is_relative_to(root/'02_VOIX_ET_ANIMATIONS'):raise ValueError('Archive hors du projet')
        allowed=target.is_relative_to(root) or (target.parent==Path.home()/'Downloads'
                                               and target.name.lower().startswith('elevenlabs_')
                                               and 'bender' in target.name.lower())
        if not allowed or target.exists() or digest(source)!=move['sha256']:
            raise ValueError('Retour impossible sans écrasement ou fichier modifié')
        target.parent.mkdir(parents=True,exist_ok=True);source.rename(target)
        move['done']=False
        manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    write_inventory(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--downloads',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.restore:restore(args.restore)
    else:
        if not args.root:parser.error('--root requis')
        data=plan(args.root,args.downloads)
        if args.apply:
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            manifest=args.root/'02_VOIX_ET_ANIMATIONS'/'_archives_rangement'/f'manifeste_{stamp}.json'
            apply(data,manifest);print('Manifeste :',manifest)
        print(json.dumps({'moves':len(data['moves']),'duplicates_archived':sum(m['duplicate'] for m in data['moves'])}))
