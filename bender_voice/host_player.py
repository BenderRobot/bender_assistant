import asyncio
import json
import shutil
import subprocess
import time
import uuid

from .hardware import HardwareBusy, HardwareError


class HostPlayer:
    def __init__(self, voice, hardware, broadcast, ownership):
        self.voice, self.hardware = voice, hardware
        self.broadcast, self.ownership = broadcast, ownership
        self.task = None
        self.process = None
        self.state = {'active': False, 'status': 'idle'}

    async def start(self, identifiers, eyes='normal', custom_eyes=None, faces=None):
        if self.task and not self.task.done():
            raise HardwareBusy('Lecture déjà en cours ; arrêter avant de relancer')
        if not shutil.which('aplay'):
            raise HardwareError('aplay absent : installer alsa-utils sur Debian')
        segments = []
        if faces is not None and len(faces)!=len(identifiers):raise ValueError('Une expression par segment audio est requise')
        for index,identifier in enumerate(identifiers):
            audio = self.voice.asset(identifier, 'wav')
            timeline = self.voice.asset(identifier, 'json')
            if not audio.is_file() or not timeline.is_file():
                raise ValueError('Enregistrement introuvable')
            data = json.loads(timeline.read_text(encoding='utf-8'))
            segments.append((audio, data, faces[index] if faces is not None else None))
        job = uuid.uuid4().hex
        self.state = {'active': True, 'status': 'starting', 'job': job}
        self.ownership(True)
        self.task = asyncio.create_task(self._run(segments, eyes, job, custom_eyes))
        return dict(self.state)

    async def _cleanup_process(self):
        process, self.process = self.process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 2)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, 2)

    async def _run(self, segments, eyes, job, custom_eyes=None):
        error = ''
        last_eyes,last_custom=eyes,custom_eyes
        try:
            for number, (audio, timeline, override) in enumerate(segments):
                selected_eyes=override['eyes'] if override else timeline.get('eyes','normal')
                if not override and selected_eyes=='normal':selected_eyes=eyes
                selected_custom=override.get('custom_eyes') if override else custom_eyes
                last_eyes,last_custom=selected_eyes,selected_custom
                self.process = subprocess.Popen(['aplay', '-q', '-D', self.hardware.status()['speaker'], str(audio)],
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                start = time.monotonic()
                while self.process.poll() is None:
                    elapsed = time.monotonic() - start
                    cue = {'pose': 0}
                    for candidate in timeline['cues']:
                        if candidate['t'] > elapsed:
                            break
                        cue = candidate
                    self.state = {'active': True, 'status': 'playing', 'job': job,
                                  'segment': number, 'elapsed': round(elapsed, 2), 'duration': timeline['duration']}
                    await self.broadcast({'pose': cue['pose'], 'eyes': selected_eyes, 'rounded': bool(cue.get('rounded')),
                                          'active': True, 'custom_eyes': selected_custom, 'playback': self.state})
                    await asyncio.sleep(.04)
                if self.process.returncode != 0:
                    raise HardwareError('Lecture ALSA impossible ; vérifier les enceintes et la sortie PCH')
                self.process = None
        except asyncio.CancelledError:
            self.state = {'active': False, 'status': 'stopped', 'job': job}
            raise
        except Exception as exc:
            error = str(exc) if isinstance(exc, HardwareError) else 'Erreur de lecture sur le Dell'
        finally:
            await self._cleanup_process()
            if self.state.get('status') != 'stopped':
                self.state = {'active': False, 'status': 'error' if error else 'finished', 'job': job, 'error': error}
            self.ownership(False)
            await self.broadcast({'pose': 0, 'eyes': last_eyes, 'custom_eyes': last_custom, 'active': False, 'playback': self.state})

    async def stop(self, job=None):
        if job is not None and self.state.get('job') != job:
            return dict(self.state)
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self._cleanup_process()
        self.ownership(False)
        if self.state.get('active'):
            self.state = {**self.state, 'active': False, 'status': 'stopped'}
            await self.broadcast({'pose': 0, 'eyes': 'normal', 'active': False, 'playback': self.state})
        return dict(self.state)
