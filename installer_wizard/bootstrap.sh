#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${JARVIS_REPO:-https://github.com/AprileNunzio/Jarvis.git}"
BRANCH="${JARVIS_BRANCH:-main}"
JARVIS_DIR=/opt/Jarvis

C='\033[0;36m'; G='\033[0;32m'; R='\033[0;31m'; N='\033[0m'
say()  { echo -e "${C}[Jarvis]${N} $*"; }
ok()   { echo -e "${G}[  OK  ]${N} $*"; }
die()  { echo -e "${R}[ERRORE]${N} $*" >&2; exit 1; }
trap 'die "Bootstrap interrotto alla riga $LINENO"' ERR

[ "$EUID" -eq 0 ] || die "Eseguire come root (sudo)."
command -v apt-get >/dev/null 2>&1 || die "Jarvis OS richiede Debian o Ubuntu."
export DEBIAN_FRONTEND=noninteractive

echo -e "${C}"
echo "   ╔═══════════════════════════════════════════╗"
echo "   ║     J.A.R.V.I.S.  —  Jarvis OS Bootstrap  ║"
echo "   ╚═══════════════════════════════════════════╝"
echo -e "${N}"

say "1/5 Riparazione e prerequisiti minimi…"
dpkg --configure -a || true
apt-get update -q
apt-get install -y -q --no-install-recommends git curl ca-certificates python3 python3-venv jq

say "2/5 Download di Jarvis OS ($BRANCH)…"
git config --global --add safe.directory "$JARVIS_DIR" || true
if [ -d "$JARVIS_DIR/.git" ]; then
    git -C "$JARVIS_DIR" fetch --quiet origin "$BRANCH"
    git -C "$JARVIS_DIR" reset --hard --quiet "origin/$BRANCH"
else
    rm -rf "$JARVIS_DIR"
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$JARVIS_DIR"
fi
ok "Repository in $JARVIS_DIR ($(git -C "$JARVIS_DIR" rev-parse --short HEAD))"

say "3/5 Configurazione di base…"
mkdir -p /etc/jarvis /var/lib/jarvis /var/log/jarvis
touch /etc/jarvis/jarvis.env
chmod 700 /etc/jarvis
chmod 600 /etc/jarvis/jarvis.env
grep -q '^JARVIS_UPDATE_BRANCH=' /etc/jarvis/jarvis.env || echo "JARVIS_UPDATE_BRANCH=$BRANCH" >> /etc/jarvis/jarvis.env
grep -q '^JARVIS_AUTO_UPDATE=' /etc/jarvis/jarvis.env || echo "JARVIS_AUTO_UPDATE=1" >> /etc/jarvis/jarvis.env

getent group jarvis-admin >/dev/null || groupadd --system jarvis-admin
for candidate in "${SUDO_USER:-}" "$(getent passwd 1000 | cut -d: -f1)"; do
    if [ -n "$candidate" ] && [ "$candidate" != "root" ] && id "$candidate" >/dev/null 2>&1; then
        usermod -aG jarvis-admin "$candidate"
        ok "Utente '$candidate' abilitato al pannello di amministrazione"
    fi
done

say "4/5 Installazione del Jarvis Supervisor…"
pkill -f 'backend/wizard_server.py' >/dev/null 2>&1 || true
systemctl disable jarvis-updater.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/jarvis-updater.service
install -m 0644 "$JARVIS_DIR/scripts/os/systemd/jarvis-supervisor.service" /etc/systemd/system/
install -m 0644 "$JARVIS_DIR/scripts/os/systemd/jarvis-rollback.service" /etc/systemd/system/
bash "$JARVIS_DIR/scripts/os/prestart.sh"
systemctl daemon-reload
systemctl enable jarvis-supervisor.service >/dev/null
systemctl restart jarvis-supervisor.service

for _ in $(seq 1 30); do
    curl -fs -o /dev/null http://127.0.0.1/healthz && break
    sleep 1
done
curl -fs -o /dev/null http://127.0.0.1/healthz || die "Il Supervisor non risponde: journalctl -u jarvis-supervisor"
ok "Supervisor attivo"

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
say "5/5 Il Supervisor sta completando l'installazione in autonomia."
echo
echo -e "   Monitor installazione / Jarvis:  ${G}http://${IP:-localhost}/${N}"
echo -e "   Pannello di amministrazione:     ${G}http://${IP:-localhost}:8080/${N}"
echo -e "   Log in tempo reale:              journalctl -fu jarvis-supervisor"
echo
