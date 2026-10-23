import array
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import wave

from bender_voice.hardware import HardwareError, HardwareBusy

FORMATS={'.wav':'wav','.mp3':'mp3','.mp4':'mov','.m4a':'mov','.mov':'mov','.ogg':'ogg','.flac':'flac','.webm':'matroska','.mkv':'matroska'}


def command(args,timeout=120):
    try:
        return subprocess.run(args,check=True,capture_output=True,timeout=timeout)
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('Lecture/conversion du média impossible ; vérifier ffmpeg et le fichier.') from exc


def prepare(catalog,identifier,progress=None):
    notify=progress or (lambda *args:None)
    notify('Vérification du format et de la durée…')
    source=catalog.original(identifier);directory=catalog.derived(identifier)
    safe=['-protocol_whitelist','file,pipe','-f',FORMATS[source.suffix]]
    info=json.loads(command(['ffprobe','-v','error',*safe,'-show_format','-show_streams','-of','json',str(source)],30).stdout)
    duration=float(info.get('format',{}).get('duration',0))
    if not math.isfinite(duration) or not 0.1<=duration<=180:raise ValueError('Utiliser des extraits entre 0,1 et 180 secondes.')
    streams=info.get('streams',[])
    if not any(s.get('codec_type')=='audio' for s in streams):raise ValueError('Cet extrait ne contient pas de piste audio.')
    audio=directory/'audio.wav'
    notify('Extraction de la piste audio avec FFmpeg…')
    command(['ffmpeg','-nostdin','-v','error','-y',*safe,'-i',str(source),'-map','0:a:0','-vn','-t','180',
             '-ac','1','-ar','16000','-c:a','pcm_s16le',str(audio)])
    with wave.open(str(audio),'rb') as wav:
        pcm=array.array('h',wav.readframes(wav.getnframes()))
        if sys.byteorder!='little':pcm.byteswap()
        duration=wav.getnframes()/wav.getframerate()
    if not pcm:raise ValueError('Piste audio vide.')
    rms=math.sqrt(sum(sample*sample for sample in pcm)/len(pcm))/32768
    metrics=dict(rms_dbfs=round(20*math.log10(max(rms,1e-9)),1),peak_dbfs=round(20*math.log10(max(max(abs(s) for s in pcm)/32768,1e-9)),1),
                 clipped_percent=round(100*sum(abs(s)>=32760 for s in pcm)/len(pcm),3))
    frames=[];warnings=[]
    video=next((s for s in streams if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')),None)
    if video:
        notify('Extraction des images de référence…',0,8)
        try:fps=float(Fraction(video.get('avg_frame_rate','25/1')))
        except (ValueError,ZeroDivisionError):fps=25
        if not math.isfinite(fps) or fps<=0:fps=25
        try:video_end=min(duration,float(video.get('duration',duration)))
        except (TypeError,ValueError):video_end=duration
        last=max(0,video_end-max(0.25,1/fps))
        for index in range(8):
            at=round(last*index/7,3);name=f'frame-{index}.jpg'
            try:
                command(['ffmpeg','-nostdin','-v','error','-y','-ss',str(at),*safe,'-i',str(source),'-map','0:v:0',
                         '-vf','scale=640:360:force_original_aspect_ratio=decrease','-frames:v','1','-q:v','3',str(directory/name)],30)
            except ValueError:
                warnings.append(f'Image à {at} s non disponible ; ce repère est ignoré.')
                notify('Images examinées (certains repères indisponibles).',index+1,8);continue
            if (directory/name).is_file():frames.append(dict(index=index,time=at,file=name))
            notify('Images de référence examinées.',index+1,8)
    return dict(duration=duration,metrics=metrics,frames=frames,audio='audio.wav',transcript='',words=[],warnings=warnings)


def transcribe(hardware,path,progress=None):
    notify=progress or (lambda *args:None)
    notify('Chargement du modèle français Vosk…')
    if not (hardware.model_dir/'am').is_dir():raise HardwareError('Modèle Vosk français absent ; installer download-models vosk puis relancer l’analyse.')
    if not hardware.lock.acquire(timeout=5):raise HardwareBusy('Micro occupé ; les samples restent en attente.')
    try:
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except ImportError as exc:raise HardwareError('Installer requirements-io.txt pour transcrire les samples.') from exc
        SetLogLevel(-1)
        if hardware.model is None:hardware.model=Model(str(hardware.model_dir))
        pieces=[];words=[]
        with wave.open(str(path),'rb') as wav:
            total=wav.getnframes();last_update=time.monotonic()
            notify('Reconnaissance locale des paroles…',0,total)
            recognizer=KaldiRecognizer(hardware.model,wav.getframerate());recognizer.SetWords(True)
            while data:=wav.readframes(4000):
                if recognizer.AcceptWaveform(data):
                    result=json.loads(recognizer.Result());pieces.append(result.get('text',''));words.extend(result.get('result',[]))
                if time.monotonic()-last_update>=0.5:
                    notify('Reconnaissance locale des paroles…',wav.tell(),total);last_update=time.monotonic()
            result=json.loads(recognizer.FinalResult());pieces.append(result.get('text',''));words.extend(result.get('result',[]))
            notify('Transcription locale terminée.',total,total)
        return ' '.join(p for p in pieces if p),words
    finally:hardware.lock.release()


def cut_audio(source,destination,start,end):
    command(['ffmpeg','-nostdin','-v','error','-y','-ss',str(start),'-i',str(source),'-t',str(end-start),
             '-ac','1','-ar','24000','-c:a','pcm_s16le',str(destination)],60)
