#!/usr/bin/env bash
set -Eeuo pipefail

JARVIS_DIR="${JARVIS_DIR:-/opt/Jarvis}"
WIZ="$JARVIS_DIR/installer_wizard"
VENV="$WIZ/venv"
REQ="$WIZ/backend/requirements.txt"
STAMP="$VENV/.requirements.sha1"

mkdir -p /etc/jarvis /var/lib/jarvis /var/log/jarvis
touch /etc/jarvis/jarvis.env
chmod 700 /etc/jarvis
chmod 600 /etc/jarvis/jarvis.env

if ! "$VENV/bin/python" -c "import fastapi, uvicorn, httpx, psutil, pam" >/dev/null 2>&1 \
        && [ -f "$STAMP" ]; then
    echo "Ambiente Python corrotto: ricostruzione"
    rm -rf "$VENV"
fi
if [ ! -x "$VENV/bin/pip" ]; then
    rm -rf "$VENV"
    python3 -m venv "$VENV"
fi
want=$(sha1sum "$REQ" | cut -c1-40)
if [ "$(cat "$STAMP" 2>/dev/null)" != "$want" ]; then
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q -r "$REQ"
    echo "$want" > "$STAMP"
fi

pkill -f 'backend/wizard_server.py' >/dev/null 2>&1 || true

if [ ! -f /etc/pam.d/jarvis-admin ]; then
    printf '%s\n' '# Jarvis OS admin panel' '@include common-auth' '@include common-account' > /etc/pam.d/jarvis-admin
fi
getent group jarvis-admin >/dev/null || groupadd --system jarvis-admin
