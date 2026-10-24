#!/usr/bin/env bash
# Focused repair: application code only; never change samples or voice.json.
set -Eeuo pipefail
trap 'code=$?; echo "Repair stopped at line $LINENO (exit $code)." >&2; exit "$code"' ERR
stage=$(cd -- "$(dirname -- "$0")/.." && pwd)
echo "Repair payload: $stage"
files=(media_api.py bender_voice/config.py bender_voice/service.py bender_voice/references.py static/media.js templates/index.html)
for file in "${files[@]}"; do
    if [[ ! -f "$stage/$file" ]]; then
        echo "Repair payload file missing: $stage/$file" >&2
        exit 1
    fi
done
case "${1:-}" in
    --check-payload) echo 'Payload files verified'; exit 0 ;;
    '') ;;
    *) echo 'Unknown repair argument' >&2; exit 2 ;;
esac
target="$HOME/applications/bender_assistant"
echo "Application: $target"
if [[ ! -x "$target/.venv/bin/python" ]]; then
    echo "Application Python missing: $target/.venv/bin/python" >&2
    exit 1
fi
backup="$HOME/.local/state/bender-reference-repairs/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$backup"
chmod 700 "$backup"
python="$target/.venv/bin/python"
"$python" - "$stage" <<'PY'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
for name in ('media_api.py','bender_voice/config.py','bender_voice/service.py','bender_voice/references.py'):
    compile((root/name).read_text(encoding='utf-8'),name,'exec')
assert 'Utiliser cette voix avec Chatterbox' in (root/'static/media.js').read_text(encoding='utf-8')
PY
sudo -v
"$python" - "$target" "$backup" "$stage" <<'PY'
import json,pathlib,shutil,sys
root,backup,stage=map(pathlib.Path,sys.argv[1:])
root=root.resolve();existing=[]
names=['media_api.py','bender_voice/config.py','bender_voice/service.py','bender_voice/references.py','static/media.js','templates/index.html']
for name in names:
    destination=root/name
    if not destination.resolve().is_relative_to(root):raise SystemExit('Unsafe target: '+name)
    if destination.exists():
        saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(destination,saved);existing.append(name)
(backup/'manifest.json').write_text(json.dumps(dict(files=names,existing=existing)),encoding='utf-8')
PY
rollback() {
    trap - ERR
    echo "Repair failed; restoring application files from $backup" >&2
    sudo systemctl stop bender.service || true
    "$python" - "$target" "$backup" <<'PY'
import json,pathlib,shutil,sys
root,backup=map(pathlib.Path,sys.argv[1:]);root=root.resolve()
data=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
for name in data['files']:
    destination=root/name
    if not destination.resolve().is_relative_to(root):raise SystemExit('Unsafe rollback target')
    if name in data['existing']:shutil.copy2(backup/name,destination)
    else:destination.unlink(missing_ok=True)
PY
    sudo systemctl start bender.service || true
    exit 1
}
trap rollback ERR
sudo systemctl stop bender.service
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$target/$file"; done
cd "$target"
"$python" - <<'PY'
from media_api import build_media_router
from bender_voice.service import VoiceService
assert any(route.path.endswith('/{identifier}/reference') for route in build_media_router().routes)
assert callable(VoiceService.activate_reference)
print('Activation API imports OK')
PY
sudo systemctl start bender.service
"$python" - <<'PY'
import json,time,urllib.request
base='http://127.0.0.1:8000'
for attempt in range(20):
    try:
        with urllib.request.urlopen(base+'/openapi.json',timeout=2) as response:spec=json.load(response)
        assert '/api/media/{identifier}/reference' in spec['paths'],'Activation route missing'
        with urllib.request.urlopen(base+'/static/media.js',timeout=2) as response:script=response.read().decode('utf-8')
        assert 'Utiliser cette voix avec Chatterbox' in script,'Activation button missing'
        with urllib.request.urlopen(base+'/api/voice/status',timeout=2) as response:status=json.load(response)
        print('VERIFIED: reference button and activation API are served')
        print('Chatterbox package installed:',status.get('chatterbox_installed'))
        break
    except Exception as error:
        if attempt==19:raise
        time.sleep(1)
PY
trap - ERR
echo "Repair verified. Backup: $backup"
echo 'Open http://192.168.1.41:8000/?v=reference-repair#samples'
