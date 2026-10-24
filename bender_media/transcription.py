"""Offline sample transcription. Model downloads happen only during setup."""
import importlib.util
import math
import os
import threading
import wave

from bender_voice.config import inside
from bender_voice.hardware import HardwareError, HardwareBusy

_lock=threading.Lock()
_model=None
_model_key=None


def profile(config):
    settings=config.get('sample_transcription',{})
    engine=settings.get('engine','whisper')
    if engine not in ('whisper','vosk'):raise ValueError('Moteur de samples : whisper ou vosk attendu.')
    model=settings.get('model','medium')
    if model not in ('base','small','medium'):raise ValueError('Modèle Whisper : base, small ou medium attendu.')
    return dict(engine='faster-whisper' if engine=='whisper' else 'vosk',model=model if engine=='whisper' else 'fr',language='fr')


def model_directory(config):
    profile(config)  # Validate the model name even when Vosk is explicitly selected.
    return inside(config['data_dir'],'models/faster-whisper-'+config.get('sample_transcription',{}).get('model','medium'))


def model_ready(directory):
    return all((directory/name).is_file() for name in ('model.bin','config.json','tokenizer.json')) and any(directory.glob('vocabulary.*'))


def status(config):
    result=profile(config)
    if result['engine']=='faster-whisper':
        result.update(installed=importlib.util.find_spec('faster_whisper') is not None,ready=model_ready(model_directory(config)))
    return result


def download(config):
    directory=model_directory(config)
    if model_ready(directory):
        print('Modèle Whisper déjà présent :',directory);return
    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:raise HardwareError('Installer requirements-samples.txt avant de télécharger Whisper.') from exc
    model=config.get('sample_transcription',{}).get('model','medium')
    size={'base':'~145 Mo','small':'~485 Mo','medium':'~1,5 Go'}[model]
    print('Téléchargement du modèle Whisper '+model+' ('+size+'). Les audios restent sur ce PC.',flush=True)
    directory.mkdir(parents=True,exist_ok=True)
    try:download_model(model,output_dir=str(directory),cache_dir=str(directory.parent/'huggingface-cache'))
    except Exception as exc:raise HardwareError('Téléchargement Whisper incomplet ; vérifier Internet puis relancer la commande.') from exc
    if not model_ready(directory):raise HardwareError('Modèle Whisper incomplet ; relancer le téléchargement.')
    print('Whisper installé : les transcriptions des samples peuvent fonctionner hors ligne.')


def transcribe(hardware,path,progress=None):
    global _model,_model_key
    if profile(hardware.config)['engine']=='vosk':
        from .processing import transcribe as vosk
        return vosk(hardware,path,progress)
    notify=progress or (lambda *args:None)
    directory=model_directory(hardware.config)
    if not model_ready(directory):raise HardwareError('Modèle Whisper absent : effectuer la mise à jour ou lancer download-models whisper sur Debian.')
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:raise HardwareError('Whisper non installé : effectuer la mise à jour ou installer requirements-samples.txt.') from exc
    if not _lock.acquire(timeout=5):raise HardwareBusy('Whisper traite déjà un extrait ; les samples restent en attente.')
    try:
        settings=hardware.config.get('sample_transcription',{})
        threads=settings.get('cpu_threads',2)
        if not isinstance(threads,int) or isinstance(threads,bool) or not 1<=threads<=8:raise ValueError('Whisper : cpu_threads doit être compris entre 1 et 8.')
        threads=min(threads,os.cpu_count() or 1)
        notify('Chargement de Whisper '+profile(hardware.config)['model']+' · français · processeur…')
        key=(str(directory),threads)
        if _model is None or _model_key!=key:
            _model=WhisperModel(str(directory),device='cpu',compute_type='int8',cpu_threads=threads,num_workers=1,local_files_only=True)
            _model_key=key
        with wave.open(str(path),'rb') as audio:duration=audio.getnframes()/audio.getframerate()
        notify('Whisper analyse les paroles en français ; le premier segment peut prendre du temps…')
        segments,_=_model.transcribe(str(path),language='fr',task='transcribe',beam_size=5,
                                     word_timestamps=True,vad_filter=True,
                                     condition_on_previous_text=False,temperature=0)
        pieces=[];words=[];covered=0
        for segment in segments:
            pieces.append(segment.text.strip())
            for word in segment.words or []:
                if math.isfinite(word.start) and math.isfinite(word.end) and 0<=word.start<word.end<=duration+0.1:
                    start,end=round(word.start,3),round(min(duration,word.end),3)
                    if start<end:
                        words.append(dict(word=word.word.strip(),start=start,end=end,conf=round(word.probability,4)))
            covered=max(covered,min(duration,segment.end))
            # End timestamp is an audio position, not a computational percentage.
            notify(f'Whisper : paroles transcrites jusqu’à {covered:.1f} s / {duration:.1f} s.')
        notify('Transcription Whisper terminée.')
        return ' '.join(piece for piece in pieces if piece),words
    except (ValueError,HardwareError):raise
    except Exception as exc:raise HardwareError('Transcription Whisper impossible ; vérifier le modèle et la mémoire disponible.') from exc
    finally:_lock.release()


def release():
    """Return model memory after a batch, leaving room for voice generation."""
    global _model,_model_key
    if _lock.acquire(blocking=False):
        try:_model=None;_model_key=None
        finally:_lock.release()
