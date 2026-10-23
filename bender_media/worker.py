from contextlib import contextmanager
import os
import threading

from bender_brain import BrainError
from bender_voice.hardware import HardwareError, HardwareBusy
from .analysis import analyze
from .processing import prepare, transcribe
from .progress import Progress


@contextmanager
def exclusive(path):
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
    with os.fdopen(fd,'r+b') as lock:
        try:
            if os.name=='nt':
                import msvcrt
                if not lock.read(1):lock.write(b'0');lock.flush()
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            yield False;return
        try:yield True
        finally:
            lock.seek(0)
            if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


class Worker:
    def __init__(self,catalog,hardware,client):
        self.catalog,self.hardware,self.client=catalog,hardware,client
        self.thread=None;self.guard=threading.Lock();self.stopping=threading.Event()
        self.message='Prêt.'

    def start(self):
        with self.guard:
            if self.thread and self.thread.is_alive():return
            self.stopping.clear()
            self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def run(self):
        with exclusive(self.catalog.root/'.worker.lock') as acquired:
            if not acquired:self.message='Un traitement est déjà actif.';return
            # Only this lock owner may recover jobs interrupted by a server restart.
            for item in self.catalog.list():
                if item['state']=='processing':
                    progress={**item['progress'],'status':'waiting','detail':'Reprise après interruption.'}
                    self.catalog.update(item['id'],state='pending',error='Reprise après interruption.',progress=progress)
            while not self.stopping.is_set() and self.catalog.automatic():
                pending=next((item for item in reversed(self.catalog.list()) if item['state']=='pending'),None)
                if not pending:self.message='Tous les nouveaux samples ont été traités.';return
                if not self.client.auth.status()['authorized']:
                    self.message='Connecter ChatGPT pour analyser les nouveaux samples.'
                    self.catalog.update(pending['id'],error=self.message,
                                        progress={**pending['progress'],'status':'waiting','detail':self.message});return
                identifier=pending['id'];self.message='Analyse de '+pending['original_name']
                self.catalog.update(identifier,state='processing',error='')
                progress=Progress(self.catalog,identifier)
                try:
                    media=pending['media']
                    progress.stage('preparation','Préparation du média…')
                    reused=bool(media.get('audio'))
                    if not reused:
                        media=prepare(self.catalog,identifier,progress.detail);self.catalog.update(identifier,media=media)
                    progress.complete('preparation',reused)
                    progress.stage('transcription','Reconnaissance locale des paroles…')
                    reused=bool(media.get('transcribed'))
                    if not media.get('transcribed'):
                        media['transcript'],media['words']=transcribe(self.hardware,self.catalog.derived(identifier)/media['audio'],progress.detail)
                        media['transcribed']=True;self.catalog.update(identifier,media=media)
                    if not media['transcript'].strip():raise ValueError('Aucune parole reconnue ; saisir une transcription puis relancer.')
                    progress.complete('transcription',reused)
                    progress.stage('analysis','GPT analyse la transcription et les images ; durée variable…')
                    report=analyze(self.client,self.catalog,self.catalog.get(identifier))
                    progress.complete('analysis')
                    progress.stop('done','Analyse terminée ; passages à vérifier et valider.')
                    self.catalog.update(identifier,state='review',analysis=report,error='')
                except HardwareBusy as exc:
                    progress.stop('waiting',str(exc))
                    self.catalog.update(identifier,state='pending',error=str(exc));self.message=str(exc);return
                except BrainError as exc:
                    progress.stop('error',str(exc))
                    self.catalog.update(identifier,state='error',error=str(exc));self.message=str(exc);return
                except (ValueError,HardwareError,OSError) as exc:
                    progress.stop('error',str(exc))
                    self.catalog.update(identifier,state='error',error=str(exc))
                except Exception:
                    progress.stop('error','Analyse interrompue ; vérifier le média et relancer.')
                    self.catalog.update(identifier,state='error',error='Analyse interrompue ; vérifier le média et relancer.')

    def status(self):
        external=any(item['state']=='processing' for item in self.catalog.list())
        return dict(active=bool(self.thread and self.thread.is_alive()) or external,
                    message='Traitement en cours sur Bender.' if external else self.message,automatic=self.catalog.automatic())
