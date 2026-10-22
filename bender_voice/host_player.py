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

    async def start(self, identifiers, eyes='normal'):
        if self.task and not self.task.done():
            raise HardwareBusy('Lecture déjà en cours ; arrêter avant de relancer')
        if not shutil.which('aplay'):
            raise HardwareError('aplay absent : installer alsa-utils sur Debian')
        segments = []
        for identifier in identifiers:
            audio = self.voice.asset(identifier, 'wav')
            timeline = self.voice.asset(identifier, 'json')
            if not audio.is_file() or not timeline.is_file():
                raise ValueError('Enregistrement introuvable')
            data = json.loads(timeline.read_text(encoding='utf-8'))
            segments.append((audio, data))
        job = uuid.uuid4().hex
        self.state = {'active': True, 'status': 'starting', 'job': job}
        self.ownership(True)
        self.task = asyncio.create_task(self._run(segments, eyes, job))
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

    async def _run(self, segments, eyes, job):
        error = ''
        try:
            for number, (audio, timeline) in enumerate(segments):
                selected_eyes = timeline.get('eyes', 'normal')
                if selected_eyes == 'normal':
                    selected_eyes = eyes
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
                                          'active': True, 'playback': self.state})
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
            await self.broadcast({'pose': 0, 'eyes': eyes, 'active': False, 'playback': self.state})

    async def stop(self):
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
