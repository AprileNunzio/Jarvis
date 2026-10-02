#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

SMB_USER=jarvis-share
OLD_ROOT=/srv/jarvis/condivisioni
ARCHIVE=/srv/jarvis/condivisa
FOLDERS=("01 Documenti" "02 Siti web" "03 Modelli 3D" "04 Codice" "05 Memoria" "06 Scambio")
CONF=/etc/samba/smb.conf

wanted() { [ "${JARVIS_SHARES:-1}" != "0" ]; }
password_hash() { printf '%s' "${JARVIS_SMB_PASSWORD:-}" | sha1sum | cut -c1-12; }

step_check() {
    wanted || return 0
    command -v smbd >/dev/null 2>&1 || return 1
    systemctl is-active --quiet smbd || return 1
    grep -q '^\[condivisa\]' "$CONF" 2>/dev/null || return 1
    grep -q '^\[memoria-jarvis\]' "$CONF" 2>/dev/null && return 1
    [ -d "$ARCHIVE/05 Memoria" ] || return 1
    [ "$(cat "$JARVIS_STATE/.shares-pass" 2>/dev/null)" = "$(password_hash)" ] || return 1
    code_current shares "$0"
}

write_conf() {
    python3 - "$CONF" "$SMB_USER" "$ARCHIVE" "$OLD_ROOT" <<'PY'
import re
import sys
from pathlib import Path

conf, user, root, old_root = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
text = conf.read_text(errors="ignore") if conf.exists() else "[global]\n   workgroup = WORKGROUP\n"
sections = re.split(r"(?m)^(?=\[)", text)
head = [s for s in sections if not s.startswith("[")]
blocks = {re.match(r"\[([^\]]+)\]", s).group(1).lower(): s for s in sections if s.startswith("[")}
glob = blocks.get("global", "[global]\n   workgroup = WORKGROUP\n")
wanted = {"server min protocol": "SMB2_10", "map to guest": "Bad User", "server signing": "auto",
          "netbios name": "JARVIS", "server string": "Jarvis", "usershare allow guests": "yes"}
for key, value in wanted.items():
    if re.search(rf"(?mi)^\s*{key}\s*=", glob):
        glob = re.sub(rf"(?mi)^\s*{key}\s*=.*$", f"   {key} = {value}", glob)
    else:
        glob = glob.rstrip("\n") + f"\n   {key} = {value}\n"
blocks["global"] = glob.rstrip("\n") + "\n\n"
for unused in ("homes", "printers", "print$", "memoria-jarvis", "file-jarvis"):
    blocks.pop(unused, None)
for key in [k for k, v in blocks.items() if re.search(rf"(?mi)^\s*path\s*=\s*{re.escape(old_root)}", v)]:
    blocks.pop(key)
common = "   browseable = yes\n   read only = no\n   create mask = 0664\n   directory mask = 2775\n   hosts allow = 127. 10. 172.16.0.0/12 192.168.\n"
blocks["condivisa"] = (f"[condivisa]\n   comment = Creazioni di Jarvis (con password)\n   path = {root}\n{common}"
                       f"   guest ok = no\n   valid users = {user}\n   force user = root\n\n")
order = ["global"] + [k for k in blocks if k != "global"]
conf.write_text("".join(head) + "".join(blocks[k] for k in order))
PY
}

move_into() {
    local src=$1 dst=$2
    [ -d "$src" ] || return 0
    mkdir -p "$dst"
    find "$src" -mindepth 1 -maxdepth 1 -print0 | while IFS= read -r -d '' item; do
        local name target
        name=$(basename "$item")
        target="$dst/$name"
        [ -e "$target" ] && target="$dst/$(date +%Y%m%d)_migrato_$name"
        mv "$item" "$target"
    done
    rmdir "$src" 2>/dev/null || true
}

migrate_old() {
    move_into "$OLD_ROOT/memoria-jarvis" "$ARCHIVE/05 Memoria"
    move_into "$OLD_ROOT/condivisa" "$ARCHIVE/06 Scambio"
    move_into /srv/jarvis/file "$ARCHIVE/01 Documenti"
    move_into /srv/jarvis/siti "$ARCHIVE/02 Siti web"
    move_into "$OLD_ROOT" "$ARCHIVE/06 Scambio"
}

step_apply() {
    if ! wanted; then
        progress 100 "Condivisioni di rete disattivate"
        return 0
    fi
    progress 15 "Installazione di Samba"
    apt_install samba
    apt_install wsdd2 >/dev/null 2>&1 || apt_install wsdd >/dev/null 2>&1 || true
    progress 35 "Utente per le condivisioni"
    if [ -z "${JARVIS_SMB_PASSWORD:-}" ]; then
        JARVIS_SMB_PASSWORD=$(python3 -c "import secrets; print(''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789') for _ in range(12)))")
        set_env JARVIS_SMB_PASSWORD "$JARVIS_SMB_PASSWORD"
    fi
    id "$SMB_USER" >/dev/null 2>&1 || useradd -M -s /usr/sbin/nologin "$SMB_USER"
    printf '%s\n%s\n' "$JARVIS_SMB_PASSWORD" "$JARVIS_SMB_PASSWORD" | smbpasswd -s -a "$SMB_USER" >/dev/null
    smbpasswd -e "$SMB_USER" >/dev/null
    progress 55 "Cartelle condivise"
    migrate_old
    local f
    for f in "${FOLDERS[@]}"; do mkdir -p "$ARCHIVE/$f"; done
    chmod 2775 "$ARCHIVE"
    if [ -f "$CONF" ] && [ ! -f "$CONF.jarvis-orig" ]; then cp "$CONF" "$CONF.jarvis-orig"; fi
    write_conf
    testparm -s >/dev/null 2>&1 || fail "Configurazione Samba non valida"
    progress 80 "Avvio dei servizi di rete"
    systemctl enable --now smbd >/dev/null 2>&1
    systemctl reload-or-restart smbd
    systemctl enable --now nmbd >/dev/null 2>&1 || true
    for unit in wsdd2 wsdd; do systemctl enable --now "$unit" >/dev/null 2>&1 && break; done
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q 'Status: active'; then
        for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
            ufw allow from "$net" to any app Samba >/dev/null 2>&1 || ufw allow from "$net" to any port 445 proto tcp >/dev/null 2>&1
            ufw allow from "$net" to any port 3702 proto udp >/dev/null 2>&1
            ufw allow from "$net" to any port 5357 proto tcp >/dev/null 2>&1
        done
    fi
    wait_for 30 systemctl is-active --quiet smbd || fail "Samba non si è avviato"
    mkdir -p "$JARVIS_STATE"
    password_hash > "$JARVIS_STATE/.shares-pass"
    code_mark shares "$0"
    progress 100 "Cartella condivisa attiva: \\\\$(hostname -I | awk '{print $1}')\\condivisa (utente $SMB_USER)"
}

step_main "$@"
