"""Native V4L2 exposure controls; no generated or reconstructed image content."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from .hardware import HardwareError, HardwareBusy

LABELS = {'brightness': 'Luminosité', 'contrast': 'Contraste', 'gain': 'Gain',
          'saturation': 'Saturation', 'sharpness': 'Netteté', 'backlight_compensation': 'Compensation du contre-jour',
          'exposure_absolute': 'Temps d’exposition', 'exposure_time_absolute': 'Temps d’exposition',
          'exposure_auto': 'Mode d’exposition', 'auto_exposure': 'Mode d’exposition',
          'white_balance_temperature_auto': 'Balance des blancs automatique',
          'white_balance_automatic': 'Balance des blancs automatique'}
AUTO_NAMES = ('exposure_auto', 'auto_exposure')
TIME_NAMES = ('exposure_absolute', 'exposure_time_absolute')


def parse_controls(output):
    controls = {}; current = None
    for line in output.splitlines():
        match = re.match(r'\s*(\w+)\s+0x[0-9a-fA-F]+\s+\(([^)]+)\)\s*:\s*(.*)', line)
        if match:
            name, kind, fields = match.groups()
            current = None
            if name not in LABELS or 'read-only' in fields or 'disabled' in fields:
                continue
            values = {key: int(value) for key, value in re.findall(r'\b(min|max|step|default|value)=(-?\d+)', fields)}
            if 'value' not in values:
                continue
            current = dict(name=name, label=LABELS[name], kind=kind, options=[], inactive='inactive' in fields, **values)
            if kind == 'bool':
                current.update(min=0, max=1, step=1)
            controls[name] = current
        elif current is not None:
            option = re.match(r'\s+(-?\d+):\s*(.+)', line)
            if option:
                current['options'].append(dict(value=int(option[1]), label=option[2].strip()))
    return controls


class Camera:
    def __init__(self, hardware):
        self.hardware = hardware
        self.path = hardware.root / 'camera-settings.json'

    @property
    def device(self):
        return self.hardware.settings.get('camera_device', '/dev/video0')

    def _run(self, *args):
        return subprocess.run(['v4l2-ctl', '--device', self.device, *args], check=True,
                              capture_output=True, text=True, timeout=5, env={**os.environ, 'LC_ALL': 'C'})

    def probe(self):
        if not shutil.which('v4l2-ctl'):
            return {}, ['v4l2-ctl absent : installer v4l-utils pour régler l’exposition.']
        try:
            return parse_controls(self._run('--list-ctrls-menus').stdout), []
        except (OSError, subprocess.SubprocessError):
            return {}, ['Réglages caméra inaccessibles ; vérifier la LifeCam et les droits vidéo.']

    def saved(self):
        if not self.path.exists():
            return {'controls': {}}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data.get('controls'), dict):
                raise ValueError()
            return data
        except (ValueError, TypeError):
            raise HardwareError('Réglages caméra illisibles ; utiliser Automatique pour les réinitialiser.')

    def _save(self, values):
        fd, name = tempfile.mkstemp(dir=self.hardware.root, prefix='.camera-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump({'controls': values}, out)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def automatic(controls, reset=False):
        values = {}
        for name in AUTO_NAMES:
            if name in controls:
                options = {item['value'] for item in controls[name]['options']}
                choice = next((value for value in (0, 3) if value in options), None)
                if choice is not None:
                    values[name] = choice
        for name in ('white_balance_temperature_auto', 'white_balance_automatic'):
            if name in controls:
                values[name] = 1
        if reset:
            for name in ('brightness', 'contrast', 'backlight_compensation'):
                if name in controls and 'default' in controls[name]:
                    values[name] = controls[name]['default']
        return values

    @staticmethod
    def validate(values, controls):
        for name, value in values.items():
            item = controls.get(name)
            if item is None or type(value) is not int:
                raise ValueError('Réglage caméra inconnu ou non pris en charge')
            if item['options']:
                if value not in {option['value'] for option in item['options']}:
                    raise ValueError('Valeur caméra non prise en charge')
            elif not item.get('min', value) <= value <= item.get('max', value) or (value - item.get('min', 0)) % item.get('step', 1):
                raise ValueError('Réglage caméra hors plage')

    def apply(self, values, controls):
        self.validate(values, controls)
        try:
            # Change modes before their dependent exposure/gain controls.
            names = sorted(values, key=lambda name: (name not in AUTO_NAMES, name))
            for name in names:
                self._run('--set-ctrl', f'{name}={values[name]}')
        except (OSError, subprocess.SubprocessError) as exc:
            raise HardwareError('Réglage refusé par la caméra ; essayer Automatique puis recharger les réglages.') from exc

    def describe(self):
        controls, warnings = self.probe()
        try:
            saved = self.saved()
        except HardwareError as exc:
            saved = {'controls': {}}; warnings.append(str(exc))
        return dict(controls=list(controls.values()), saved=saved['controls'], warnings=warnings,
                    warmup_seconds=2, preferred_size='1280x720', fallback_size='640x480')

    def update(self, action='custom', values=None):
        if not self.hardware.lock.acquire(blocking=False):
            raise HardwareBusy('Terminer la capture en cours avant de régler la caméra')
        try:
            controls, warnings = self.probe()
            if not controls:
                raise HardwareError(warnings[0] if warnings else 'Aucun réglage disponible sur cette caméra')
            if action == 'auto':
                values = self.automatic(controls, reset=True)
                combined = values
            else:
                combined = self.saved()['controls']
                if action in ('darker', 'brighter'):
                    name = next((name for name in TIME_NAMES if name in controls), None)
                    mode = next((name for name in AUTO_NAMES if name in controls and 1 in {option['value'] for option in controls[name]['options']}), None)
                    if name and mode:
                        item = controls[name]
                        value = round(item['value'] * (0.65 if action == 'darker' else 1.5))
                        step = item.get('step', 1)
                        value = item['min'] + round((value - item['min']) / step) * step
                        values = {mode: 1, name: max(item['min'], min(item['max'], value))}
                    else:
                        raise HardwareError('Le réglage manuel de l’exposition n’est pas proposé par cette caméra.')
                values = values or {}
                combined = {**combined, **values}
                mode = next((name for name in AUTO_NAMES if name in controls), None)
                if mode and combined.get(mode, controls[mode]['value']) != 1:
                    if any(name in values for name in TIME_NAMES):
                        raise ValueError('Choisir le mode manuel pour modifier le temps d’exposition')
                    # A stored manual time must not be reapplied after switching to auto.
                    combined = {name: value for name, value in combined.items() if name not in TIME_NAMES}
            self.apply(values, controls)
            self._save(combined)
            return self.describe()
        finally:
            self.hardware.lock.release()

    def prepare(self):
        """Called with the capture lock held; never silently ignore saved controls."""
        controls, warnings = self.probe()
        saved = self.saved()['controls']
        values = saved or self.automatic(controls)
        if values:
            self.apply(values, controls)
        size = '640x480'
        if shutil.which('v4l2-ctl'):
            try:
                formats = self._run('--list-formats-ext').stdout
                mjpeg = re.search(r"\[\d+\]:\s*'MJPG'(.*?)(?=\n\s*\[\d+\]:|\Z)", formats, re.S)
                if mjpeg and re.search(r'Size:\s*Discrete\s+1280x720\b', mjpeg[1]):
                    size = '1280x720'
            except (OSError, subprocess.SubprocessError):
                warnings.append('Formats caméra non disponibles ; capture en 640 × 480.')
        return size, warnings
