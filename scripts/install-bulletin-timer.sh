#!/usr/bin/env bash
set -euo pipefail
target=$(cd -- "$(dirname -- "$0")/.." && pwd)
unit=$(mktemp --suffix=.service)
timer=$(mktemp --suffix=.timer)
trap 'rm -f "$unit" "$timer"' EXIT
cat > "$unit" <<EOF
[Unit]
Description=Bender preparation des bulletins audio locaux
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$target
EnvironmentFile=-$target/.env
EnvironmentFile=-$target/.env.elevenlabs
Environment=OMP_NUM_THREADS=2
Environment=MKL_NUM_THREADS=2
ExecStart=/usr/bin/env "BENDER_VOICE_CONFIG=$target/voice.json" "$target/.venv/bin/python" -m bender_voice prepare-news
Nice=15
UMask=0077
TimeoutStartSec=3h
EOF
cat > "$timer" <<'EOF'
[Unit]
Description=Bender verification de la preparation planifiee
[Timer]
OnCalendar=*-*-* *:*:00
Persistent=true
AccuracySec=10s
Unit=bender-bulletins.service
[Install]
WantedBy=timers.target
EOF
systemd-analyze verify "$unit"
sudo install -m 644 "$unit" /etc/systemd/system/bender-bulletins.service
sudo install -m 644 "$timer" /etc/systemd/system/bender-bulletins.timer
sudo systemctl daemon-reload
sudo systemctl enable --now bender-bulletins.timer
echo 'Bulletin worker installed; configure RSS and enable the schedule in the workshop.'
