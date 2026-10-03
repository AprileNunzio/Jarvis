#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

IMAGE=jarvis-sandbox:local
BASE_IMAGE=python:3.11-slim-bookworm
UNIT_SRC="$JARVIS_DIR/scripts/os/systemd/jarvis-sandbox.service"
UNIT_DST=/etc/systemd/system/jarvis-sandbox.service
DAEMON_JSON=/etc/docker/daemon.json
RUNSC_BIN=/usr/local/bin/runsc
SOCKET=/run/jarvis/sandbox/broker.sock

sources() {
    find "$JARVIS_DIR/sandbox_broker" "$JARVIS_DIR/server/features/sandbox" -name '*.py' | sort
    echo "$UNIT_SRC"
    echo "$JARVIS_DIR/docker/sandbox/Dockerfile"
}

service_active() { systemctl is-active --quiet jarvis-sandbox; }

step_check() {
    code_current sandbox $(sources) \
        && docker image inspect "$IMAGE" >/dev/null 2>&1 \
        && service_active \
        && [ -S "$SOCKET" ]
}

fetch_runsc() {
    local arch url tmp
    arch=$(uname -m)
    case "$arch" in x86_64|aarch64) ;; *) return 1 ;; esac
    url="https://storage.googleapis.com/gvisor/releases/release/latest/$arch"
    tmp=$(mktemp -d)
    if retry 3 5 curl -fsSL -o "$tmp/runsc" "$url/runsc" \
        && retry 3 5 curl -fsSL -o "$tmp/runsc.sha512" "$url/runsc.sha512" \
        && (cd "$tmp" && sha512sum -c runsc.sha512 >/dev/null); then
        install -m 0755 "$tmp/runsc" "$RUNSC_BIN"
        rm -rf "$tmp"
        return 0
    fi
    rm -rf "$tmp"
    return 1
}

register_runtime() {
    python3 - "$DAEMON_JSON" "$RUNSC_BIN" <<'PY'
import json
import os
import sys

path, runsc = sys.argv[1], sys.argv[2]
config = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
runtimes = config.setdefault("runtimes", {})
if runtimes.get("runsc", {}).get("path") == runsc:
    sys.exit(3)
runtimes["runsc"] = {"path": runsc}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2)
    handle.write("\n")
PY
}

setup_gvisor() {
    [ -x "$RUNSC_BIN" ] || fetch_runsc || return 1
    local rc=0
    register_runtime || rc=$?
    case "$rc" in
        0) systemctl restart docker && wait_for 60 docker info ;;
        3) return 0 ;;
        *) return 1 ;;
    esac
}

step_apply() {
    progress 5 "Verifica prerequisiti"
    apt_install python3 curl ca-certificates
    docker info >/dev/null 2>&1 || fail "Docker non risponde"

    progress 15 "Immagine di base"
    retry 3 10 docker pull "$BASE_IMAGE" >/dev/null || warn "Pull dell'immagine base non riuscito: uso la copia locale se presente"

    progress 35 "Immagine della sandbox"
    docker build --quiet -t "$IMAGE" "$JARVIS_DIR/docker/sandbox" >/dev/null || fail "Build dell'immagine sandbox non riuscita"

    progress 55 "Isolamento gVisor"
    if setup_gvisor; then
        info "gVisor registrato in Docker"
    else
        warn "gVisor non disponibile: la sandbox userà il container rinforzato"
    fi

    progress 80 "Servizio Sandbox Broker"
    install -m 0644 "$UNIT_SRC" "$UNIT_DST"
    systemctl daemon-reload
    systemctl enable jarvis-sandbox >/dev/null 2>&1
    systemctl restart jarvis-sandbox
    wait_for 60 test -S "$SOCKET" || fail "Il Sandbox Broker non si è avviato: journalctl -u jarvis-sandbox"

    code_mark sandbox $(sources)
    progress 100 "Sandbox isolata attiva"
}

step_main "$@"
