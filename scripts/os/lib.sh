#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C.UTF-8

JARVIS_DIR="${JARVIS_DIR:-/opt/Jarvis}"
JARVIS_ETC="${JARVIS_ETC:-/etc/jarvis}"
JARVIS_STATE="${JARVIS_STATE:-/var/lib/jarvis}"
JARVIS_ENV_FILE="$JARVIS_ETC/jarvis.env"
JARVIS_KIOSK_USER="${JARVIS_KIOSK_USER:-jarvis-kiosk}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
CORE_URL="${CORE_URL:-http://127.0.0.1:8443}"

if [ -f "$JARVIS_ENV_FILE" ]; then
    set -a; . "$JARVIS_ENV_FILE"; set +a
fi

if [ -n "${JARVIS_OLLAMA_URL:-}" ]; then
    OLLAMA_URL="${JARVIS_OLLAMA_URL%/}"
    case "$OLLAMA_URL" in http://*|https://*) ;; *) OLLAMA_URL="http://$OLLAMA_URL" ;; esac
    case "${OLLAMA_URL#*//}" in *:*) ;; *) OLLAMA_URL="$OLLAMA_URL:11434" ;; esac
fi

ollama_remote() {
    local host="${OLLAMA_URL#*//}"
    host="${host%%:*}"
    case "$host" in 127.0.0.1|localhost|"") return 1 ;; *) return 0 ;; esac
}

progress() { echo "@@PROGRESS $1 ${*:2}"; }
detail()   { echo "@@DETAIL $*"; }
info()     { echo "[INFO] $*"; }
warn()     { echo "[WARN] $*"; }
fail()     { echo "[FAIL] $*"; exit 1; }

retry() {
    local attempts=$1 delay=$2 i
    shift 2
    for ((i = 1; i <= attempts; i++)); do
        "$@" && return 0
        if [ "$i" -lt "$attempts" ]; then
            warn "Tentativo $i/$attempts fallito: $*. Nuovo tentativo tra ${delay}s"
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done
    return 1
}

wait_for() {
    local timeout=$1 t=0
    shift
    until "$@" >/dev/null 2>&1; do
        t=$((t + 2))
        [ "$t" -ge "$timeout" ] && return 1
        sleep 2
    done
}

apt_heal() {
    warn "Auto-riparazione del gestore pacchetti…"
    rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock 2>/dev/null || true
    dpkg --configure -a || true
    apt-get -f install -y -q || true
}

pkgs_present() {
    local p
    for p in "$@"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || return 1
    done
}

apt_install() {
    local missing=() p
    for p in "$@"; do
        pkgs_present "$p" || missing+=("$p")
    done
    [ ${#missing[@]} -eq 0 ] && return 0
    info "Pacchetti da installare: ${missing[*]}"
    retry 3 5 apt-get update -q || { apt_heal; apt-get update -q; }
    if ! retry 2 5 apt-get install -y -q --no-install-recommends "${missing[@]}"; then
        apt_heal
        apt-get install -y -q --no-install-recommends "${missing[@]}"
    fi
}

set_env() {
    local key=$1 value=$2
    mkdir -p "$JARVIS_ETC"
    touch "$JARVIS_ENV_FILE"
    chmod 600 "$JARVIS_ENV_FILE"
    if grep -q "^${key}=" "$JARVIS_ENV_FILE"; then
        local tmp
        tmp=$(mktemp)
        awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k {print k "=" v; next} {print}' "$JARVIS_ENV_FILE" > "$tmp"
        cat "$tmp" > "$JARVIS_ENV_FILE"
        rm -f "$tmp"
    else
        echo "${key}=${value}" >> "$JARVIS_ENV_FILE"
    fi
    export "$key=$value"
}

write_if_changed() {
    local path=$1 mode=${2:-0644} tmp
    tmp=$(mktemp)
    cat > "$tmp"
    if [ -f "$path" ] && cmp -s "$tmp" "$path"; then
        rm -f "$tmp"
        return 1
    fi
    install -D -m "$mode" "$tmp" "$path"
    rm -f "$tmp"
    return 0
}

same_content() {
    local tmp rc=0
    tmp=$(mktemp)
    cat > "$tmp"
    [ -f "$1" ] && cmp -s "$tmp" "$1" || rc=1
    rm -f "$tmp"
    return $rc
}

_code_hash() { cat "$@" 2>/dev/null | sha1sum | cut -c1-16; }
code_current() { local name=$1; shift; [ "$(cat "$JARVIS_STATE/.code-$name" 2>/dev/null)" = "$(_code_hash "$@")" ]; }
code_mark() { local name=$1; shift; mkdir -p "$JARVIS_STATE"; _code_hash "$@" > "$JARVIS_STATE/.code-$name"; }

compose() {
    docker compose \
        --project-name jarvis \
        --project-directory "$JARVIS_DIR/docker" \
        -f "$JARVIS_DIR/docker/docker-compose.yml" \
        --env-file "$JARVIS_ENV_FILE" "$@"
}

has_nvidia_gpu() {
    command -v lspci >/dev/null 2>&1 && lspci | grep -qiE '(vga|3d).*nvidia'
}

has_usable_gpu() {
    command -v nvidia-smi >/dev/null 2>&1 || return 1
    local info cap vram
    info=$(nvidia-smi --query-gpu=compute_cap,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1) || return 1
    cap=$(echo "$info" | cut -d, -f1 | tr -d ' ')
    vram=$(echo "$info" | cut -d, -f2 | tr -d ' ')
    [ -n "$cap" ] && [ -n "$vram" ] || return 1
    awk -v c="$cap" -v v="$vram" 'BEGIN { exit !(c + 0 >= 5.0 && v + 0 >= 4000) }'
}

hw_profile() { if has_usable_gpu; then echo gpu; else echo cpu; fi; }

core_src_hash() {
    (
        cd "$JARVIS_DIR"
        git -c safe.directory='*' rev-parse HEAD:server HEAD:docker/core 2>/dev/null | sha1sum | cut -c1-16
    )
}

step_main() {
    case "${1:-}" in
        check) step_check ;;
        apply) step_apply ;;
        *) echo "Uso: $0 check|apply" >&2; exit 2 ;;
    esac
}
