"""Extract a separate, strictly data-only reference archive."""
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path


def install_reference_archive(archive_path, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 64 or sum(m.size for m in members) > 200 * 1024 * 1024:
            raise ValueError('Archive de références trop volumineuse')
        seen = set()
        for member in members:
            if not member.isfile() or not re.fullmatch(r'[A-Za-z0-9_-]+\.(wav|json)', member.name) or member.name in seen:
                raise ValueError('Archive de références invalide')
            seen.add(member.name)
        if 'catalog.json' not in seen:
            raise ValueError('Catalogue de références manquant')
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            staging = Path(temporary)
            for member in members:
                with archive.extractfile(member) as source, (staging / member.name).open('wb') as output:
                    shutil.copyfileobj(source, output)
            entries = json.loads((staging / 'catalog.json').read_text(encoding='utf-8'))
            if not isinstance(entries, list): raise ValueError('Catalogue invalide')
            for entry in entries:
                required = [entry['audio'], *entry.get('methods', {}).values()]
                if not all(name in seen for name in required): raise ValueError('Média absent du catalogue')
            destination.mkdir(parents=True, exist_ok=True)
            # Publish catalog last, after all its referenced files are ready.
            for name in sorted(seen - {'catalog.json'}) + ['catalog.json']:
                (staging / name).replace(destination / name)
    return len(entries)
