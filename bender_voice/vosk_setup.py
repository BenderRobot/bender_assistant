"""Téléchargement explicite du petit modèle français Vosk, hors génération."""
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .hardware import Hardware


def download_vosk(config):
    target = Hardware(config).model_dir
    if target.exists():
        if (target / 'am').is_dir():
            print('Modèle Vosk déjà présent')
            return
        raise ValueError('Dossier Vosk incomplet existant ; choisir un autre vosk_model_dir')
    target.parent.mkdir(parents=True, exist_ok=True)
    url = 'https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip'
    print('Téléchargement du modèle français Vosk (~41 Mo)…', flush=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        directory = Path(directory).resolve()
        archive_path = directory / 'model.zip'
        with urllib.request.urlopen(url, timeout=60) as source, archive_path.open('wb') as out:
            shutil.copyfileobj(source, out)
        with zipfile.ZipFile(archive_path) as archive:
            if sum(info.file_size for info in archive.infolist()) > 500_000_000:
                raise ValueError('Archive Vosk trop volumineuse')
            for info in archive.infolist():
                destination = (directory / info.filename).resolve()
                if not destination.is_relative_to(directory) or stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError('Chemin invalide dans le modèle Vosk')
            archive.extractall(directory)
        model = directory / 'vosk-model-small-fr-0.22'
        if not (model / 'am').is_dir():
            raise ValueError('Archive Vosk incomplète')
        shutil.move(str(model), str(target))
    print('Modèle Vosk installé : reconnaissance locale prête')
