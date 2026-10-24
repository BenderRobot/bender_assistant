#!/usr/bin/env bash
set -euo pipefail
relative=${1:?Chemin requis}
revision=${2:?Revision requise}
[[ "$relative" =~ ^[a-zA-Z0-9_/-]+$ && "$relative" != /* && "$relative" != *..* && "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 2
target="$HOME/$relative"
stage="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$target" "$HOME/.local/state/bender-backups"
# Validate all archive paths before changing the installed application.
python3 - "$stage/release.tar.gz" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1]) as archive:
    for member in archive.getmembers():
        p = PurePosixPath(member.name)
        if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk():
            raise SystemExit('Archive non sure')
        if any(x in {'data', 'models', '.git', '.env', 'voice.json', 'bender_memory.db'} or x.startswith('.venv') for x in p.parts):
            raise SystemExit('Archive contenant des donnees privees')
        if any(x.startswith('.env.') and x != '.env.example' for x in p.parts):
            raise SystemExit('Archive contenant une configuration privee')
PY
sudo -v
if systemctl cat bender-media.service >/dev/null 2>&1; then sudo systemctl stop bender-media.service; fi
if systemctl cat bender-bulletins.timer >/dev/null 2>&1; then sudo systemctl stop bender-bulletins.timer; fi
if systemctl cat bender-bulletins.service >/dev/null 2>&1; then sudo systemctl stop bender-bulletins.service; fi
backup="$HOME/.local/state/bender-backups/$(date +%Y%m%d-%H%M%S)-$$.tar.gz"
tar -czf "$backup" --exclude='./.venv*' --exclude='./data' --exclude='./models' --exclude='./.git' -C "$target" .
chmod 600 "$backup"
had_service=false
if systemctl cat bender.service >/dev/null 2>&1; then
    had_service=true
    sudo systemctl stop bender.service
else
    # Stop only this user's Python server in this exact installation directory.
    python3 - "$target" <<'PY'
import os, pathlib, signal, sys
target = pathlib.Path(sys.argv[1]).resolve()
for entry in pathlib.Path('/proc').iterdir():
    if not entry.name.isdigit(): continue
    try:
        if entry.stat().st_uid != os.getuid() or (entry/'cwd').resolve() != target: continue
        args = (entry/'cmdline').read_bytes().split(b'\0')
        if b'server.py' in args and b'python' in pathlib.Path(os.fsdecode(args[0])).name.encode():
            os.kill(int(entry.name), signal.SIGTERM)
    except (OSError, ProcessLookupError): pass
PY
fi
trap 'echo "Echec de mise a jour. Sauvegarde : $backup" >&2; if "$had_service"; then sudo systemctl start bender.service || true; fi' ERR
tar -xzf "$stage/release.tar.gz" -C "$target"
cd "$target"
if [[ -f "$stage/elevenlabs.env" ]]; then
  install -m 600 "$stage/elevenlabs.env" "$target/.env.elevenlabs"
  rm -f "$stage/elevenlabs.env"
fi
if [[ -f "$stage/reference-samples.tar.gz" ]]; then
  python3 - "$stage/reference-samples.tar.gz" "$target/data/reference_samples" <<'PY'
import sys
from reference_media import install_reference_archive
print('Références installées :', install_reference_archive(sys.argv[1], sys.argv[2]))
PY
fi
bash scripts/install-debian.sh --system-deps --micro --samples
if [[ -f "$stage/elevenlabs-settings.json" ]]; then
  BENDER_VOICE_CONFIG=voice.json .venv/bin/python scripts/install-elevenlabs-settings.py "$stage/elevenlabs-settings.json"
  rm -f "$stage/elevenlabs-settings.json"
fi
if [[ -f "$stage/media-inbox.tar.gz" ]]; then
  BENDER_VOICE_CONFIG=voice.json .venv/bin/python -m bender_media import-archive "$stage/media-inbox.tar.gz"
fi
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
# WorkingDirectory and EnvironmentFile take literal paths, not shell quotes.
unit=$(mktemp --suffix=.service)
cat > "$unit" <<EOF
[Unit]
Description=Bender voix et visage
After=network.target sound.target
[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$target
EnvironmentFile=-$target/.env
EnvironmentFile=-$target/.env.elevenlabs
# EnvironmentFile overrides Environment=; set deployment values on the process.
ExecStart=/usr/bin/env BENDER_HOST=0.0.0.0 BENDER_PORT=8000 BENDER_REVISION=$revision "BENDER_VOICE_CONFIG=$target/voice.json" "$target/.venv/bin/python" "$target/server.py"
Restart=on-failure
RestartSec=5
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify "$unit"
sudo install -m 644 "$unit" /etc/systemd/system/bender.service
rm -f "$unit"
media_unit=$(mktemp --suffix=.service)
cat > "$media_unit" <<EOF
[Unit]
Description=Bender analyse des nouveaux samples
After=network.target bender.service
[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$target
EnvironmentFile=-$target/.env
EnvironmentFile=-$target/.env.elevenlabs
ExecStart=/usr/bin/env "BENDER_VOICE_CONFIG=$target/voice.json" "$target/.venv/bin/python" -m bender_media process-pending
UMask=0077
Nice=10
TimeoutStartSec=infinity
[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify "$media_unit"
sudo install -m 644 "$media_unit" /etc/systemd/system/bender-media.service
rm -f "$media_unit"
bash scripts/install-bulletin-timer.sh
sudo systemctl daemon-reload
sudo systemctl enable --now bender.service
sudo systemctl enable bender-media.service
healthy=false
for attempt in {1..30}; do
    if .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/voice/status',timeout=2).read()" 2>/dev/null; then healthy=true; break; fi
    sleep 1
done
if ! "$healthy"; then sudo journalctl -u bender.service -n 30 --no-pager; false; fi
.venv/bin/python scripts/verify-deployment.py http://127.0.0.1:8000 "$revision"
printf '%s\n' "$revision" > DEPLOYED_COMMIT
sudo systemctl start --no-block bender-media.service
echo "Version $revision active. Sauvegarde : $backup"
