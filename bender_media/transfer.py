"""Standard-library-only archives: originals outside Git, hashed and validated."""
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from .catalog import Catalog, EXTENSIONS, MAX_FILE, MAX_BATCH, digest_file


def pack(source, archive_path, known=()):
    source=Path(source);known=set(known);entries={};total=0
    if not source.is_dir():return 0
    for path in sorted(source.rglob('*')):
        if path.is_symlink():continue
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:continue
        if not path.resolve().is_relative_to(source.resolve()):raise ValueError('Fichier hors du dossier de dépôt')
        size=path.stat().st_size
        if not 0<size<=MAX_FILE:raise ValueError(f'Média vide ou supérieur à 100 Mo : {path.name}')
        identifier=digest_file(path)
        if identifier in known or identifier in entries:continue
        total+=size
        if total>MAX_BATCH:raise ValueError('Plus de 500 Mo de nouveaux médias ; répartir les ajouts sur plusieurs mises à jour')
        entries[identifier]=(path,dict(id=identifier,name=path.name,extension=path.suffix.lower(),size=size))
    if not entries:return 0
    if len(entries)>100:raise ValueError('Limiter un import à 100 nouveaux fichiers')
    with tempfile.TemporaryDirectory() as temporary:
        manifest=Path(temporary)/'manifest.json'
        manifest.write_text(json.dumps([item[1] for item in entries.values()],ensure_ascii=False),encoding='utf-8')
        with tarfile.open(archive_path,'w:gz') as archive:
            archive.add(manifest,arcname='manifest.json',recursive=False)
            for identifier,(path,item) in entries.items():
                archive.add(path,arcname=identifier+item['extension'],recursive=False)
    return len(entries)


def install(archive_path,catalog):
    count=0
    with tarfile.open(archive_path,'r:gz') as archive:
        members=archive.getmembers()
        if len(members)>101 or sum(m.size for m in members)>MAX_BATCH+100_000:
            raise ValueError('Archive de médias trop volumineuse')
        names=set()
        for member in members:
            if not member.isfile() or member.name in names or not 0<=member.size<=MAX_FILE or (member.name!='manifest.json' and not re.fullmatch(r'[a-f0-9]{64}\.[a-z0-9]+',member.name)):
                raise ValueError('Archive de médias invalide')
            names.add(member.name)
        if 'manifest.json' not in names or archive.getmember('manifest.json').size>100_000:raise ValueError('Catalogue de transfert manquant ou trop grand')
        manifest=json.loads(archive.extractfile('manifest.json').read().decode('utf-8'))
        if not isinstance(manifest,list) or len(manifest)>100:raise ValueError('Catalogue de transfert invalide')
        with tempfile.TemporaryDirectory(dir=catalog.root) as temporary:
            staging=Path(temporary);validated=[];seen=set()
            for entry in manifest:
                identifier=entry['id'];extension=entry['extension'];name=identifier+extension
                if not re.fullmatch(r'[a-f0-9]{64}',identifier) or extension not in EXTENSIONS or name not in names or identifier in seen:
                    raise ValueError('Média non conforme au catalogue')
                if not isinstance(entry['name'],str) or not 0<len(entry['name'])<=255 or Path(entry['name']).name!=entry['name'] or '/' in entry['name'] or '\\' in entry['name']:
                    raise ValueError('Nom de média invalide')
                seen.add(identifier)
                if archive.getmember(name).size!=entry['size'] or not 0<entry['size']<=MAX_FILE:raise ValueError('Taille de média incorrecte')
                with archive.extractfile(name) as src,(staging/name).open('wb') as target:shutil.copyfileobj(src,target)
                if digest_file(staging/name)!=identifier:raise ValueError('Empreinte du média incorrecte')
                validated.append((entry,staging/name))
            if names!={'manifest.json',*(p.name for _,p in validated)}:raise ValueError('Fichier inattendu dans l’archive')
            existing=set(catalog.inventory())
            for entry,path in validated:
                identifier=entry['id']
                if identifier in existing:continue
                path.replace(catalog.root/'originals'/path.name)
                catalog.add(identifier,entry['name'],entry['extension']);count+=1
    return count
