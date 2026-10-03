#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

DAEMON_JSON=/etc/docker/daemon.json
GVISOR_DIR=/usr/local/bin
RUNSC_BIN="$GVISOR_DIR/runsc"
GVISOR_BASE=https://storage.googleapis.com/gvisor/releases/release/latest
TRIED_FILE="$JARVIS_STATE/.gvisor-tried"
RETRY_AFTER_SECONDS=21600

runtime_registered() {
    docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"runsc"'
}

unsupported_arch() {
    case "$(uname -m)" in x86_64|aarch64) return 1 ;; *) return 0 ;; esac
}

tried_recently() {
    [ -f "$TRIED_FILE" ] && [ $(( $(date +%s) - $(stat -c %Y "$TRIED_FILE") )) -lt "$RETRY_AFTER_SECONDS" ]
}

step_check() {
    unsupported_arch && return 0
    [ -x "$RUNSC_BIN" ] && runtime_registered && return 0
    tried_recently
}

fetch_runsc() {
    local arch url tmp
    arch=$(uname -m)
    command -v bzip2 >/dev/null 2>&1 || apt_install bzip2 || return 1
    url="$GVISOR_BASE/$arch"
    tmp=$(mktemp -d)
    if retry 4 15 curl -fsSL --connect-timeout 20 -C - -o "$tmp/gvisor.tar.bz2" "$url/gvisor.tar.bz2" \
        && retry 3 5 curl -fsSL -o "$tmp/gvisor.tar.bz2.sha512" "$url/gvisor.tar.bz2.sha512" \
        && (cd "$tmp" && sha512sum -c gvisor.tar.bz2.sha512 >/dev/null) \
        && tar -xjf "$tmp/gvisor.tar.bz2" -C "$GVISOR_DIR" runsc containerd-shim-runsc-v1 gvisor-bin; then
        chmod 0755 "$RUNSC_BIN"
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

step_apply() {
    mkdir -p "$JARVIS_STATE"
    touch "$TRIED_FILE"
    progress 10 "Download di gVisor"
    if [ ! -x "$RUNSC_BIN" ] && ! fetch_runsc; then
        warn "gVisor non scaricabile ora: nuovo tentativo tra qualche ora, intanto la sandbox usa il container rinforzato"
        exit 0
    fi
    progress 80 "Registrazione del runtime"
    local rc=0
    register_runtime || rc=$?
    case "$rc" in
        0) systemctl restart docker && wait_for 60 docker info || warn "Docker non è ripartito subito" ;;
        3) ;;
        *) warn "Registrazione del runtime gVisor non riuscita"; exit 0 ;;
    esac
    progress 100 "gVisor registrato"
}

step_main "$@"
