#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

free_disk_mb() { df -Pm / | awk 'NR==2 {print $4}'; }

step_check() {
    [ -n "${JARVIS_LLM_MODEL:-}" ] && [ -n "${JARVIS_LLM_FAST_MODEL:-}" ] && [ -n "${JARVIS_EMBED_MODEL:-}" ] \
        && [ "$(free_disk_mb)" -gt 3072 ] \
        && [ "${JARVIS_HW_PROFILE:-}" = "$(hw_profile)" ]
}

select_llm() {
    local ram_gb=$1 vram_gb=$2
    if   [ "$vram_gb" -ge 20 ]; then echo "qwen2.5:14b"
    elif [ "$vram_gb" -ge 8 ] || [ "$ram_gb" -ge 24 ]; then echo "qwen2.5:7b"
    elif [ "$ram_gb" -ge 7 ]; then echo "qwen2.5:3b"
    else echo "qwen2.5:1.5b"
    fi
}

select_fast_llm() {
    local ram_gb=$1 vram_gb=$2
    if   [ "$vram_gb" -ge 6 ]; then echo "qwen2.5:3b"
    elif [ "$ram_gb" -ge 6 ]; then echo "qwen2.5:1.5b"
    else echo "qwen2.5:0.5b"
    fi
}

step_apply() {
    progress 10 "Analisi architettura"
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64|aarch64) info "Architettura: $arch" ;;
        *) fail "Architettura non supportata: $arch (richiesto x86_64 o aarch64)" ;;
    esac
    command -v apt-get >/dev/null 2>&1 || fail "Jarvis OS richiede una distribuzione Debian/Ubuntu"
    . /etc/os-release
    info "Sistema operativo: ${PRETTY_NAME:-$ID}"

    progress 30 "Verifica connessione Internet"
    retry 5 3 curl -fsS --max-time 10 -o /dev/null https://github.com \
        || fail "Nessuna connessione a Internet: impossibile scaricare i componenti"
    info "Connessione Internet OK"

    progress 55 "Analisi risorse hardware"
    local ram_gb cores disk_mb vram_gb=0 profile=cpu
    ram_gb=$(awk '/MemTotal/ {printf "%d", ($2 / 1024 / 1024) + 0.5}' /proc/meminfo)
    cores=$(nproc)
    disk_mb=$(free_disk_mb)
    info "CPU: $cores core — RAM: ${ram_gb} GB — Disco libero: $((disk_mb / 1024)) GB"
    [ "$disk_mb" -lt 3072 ] && fail "Spazio su disco insufficiente: servono almeno 3 GB liberi"
    [ "$disk_mb" -lt 20480 ] && warn "Spazio su disco ridotto: consigliati almeno 20 GB"
    [ "$ram_gb" -lt 4 ] && warn "RAM ridotta (${ram_gb} GB): prestazioni neurali limitate"

    if has_usable_gpu; then
        profile=gpu
        vram_gb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
            | head -1 | awk '{printf "%d", $1 / 1024}')
        info "GPU NVIDIA utilizzabile: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1) (VRAM: ${vram_gb} GB)"
    elif has_nvidia_gpu; then
        warn "Scheda NVIDIA rilevata ($(lspci | grep -iE '(vga|3d).*nvidia' | head -1 | cut -d: -f3- | xargs))"
        warn "ma non utilizzabile per l'inferenza (driver proprietario assente o GPU troppo datata/poca VRAM):"
        warn "Jarvis usa la modalità CPU. Con una GPU recente e il driver NVIDIA verrà attivata da sola al riavvio."
    else
        info "Nessuna GPU NVIDIA: modalità inferenza CPU ottimizzata"
    fi

    progress 80 "Selezione reti neurali ottimali"
    JARVIS_HW_PROFILE_PREV="${JARVIS_HW_PROFILE:-}"
    set_env JARVIS_HW_PROFILE "$profile"
    if [ "$profile" = gpu ]; then set_env COMPOSE_PROFILES gpu; else set_env COMPOSE_PROFILES ""; fi
    if [ -n "${JARVIS_HW_PROFILE_PREV:-}" ] && [ "$JARVIS_HW_PROFILE_PREV" != "$profile" ] \
            && [ "${JARVIS_LLM_MODEL_AUTO:-1}" = "1" ]; then
        JARVIS_LLM_MODEL=""
    fi
    if [ -n "${JARVIS_HW_PROFILE_PREV:-}" ] && [ "$JARVIS_HW_PROFILE_PREV" != "$profile" ] \
            && [ "${JARVIS_LLM_FAST_AUTO:-1}" = "1" ]; then
        JARVIS_LLM_FAST_MODEL=""
    fi
    if [ -z "${JARVIS_LLM_MODEL:-}" ]; then
        set_env JARVIS_LLM_MODEL "$(select_llm "$ram_gb" "${vram_gb:-0}")"
    fi
    if [ -z "${JARVIS_LLM_FAST_MODEL:-}" ]; then
        set_env JARVIS_LLM_FAST_MODEL "$(select_fast_llm "$ram_gb" "${vram_gb:-0}")"
    fi
    if [ -z "${JARVIS_EMBED_MODEL:-}" ]; then
        set_env JARVIS_EMBED_MODEL "nomic-embed-text"
    fi
    info "Cervello potente: $JARVIS_LLM_MODEL — veloce: $JARVIS_LLM_FAST_MODEL — Embedding: $JARVIS_EMBED_MODEL"
    progress 100 "Analisi completata"
}

step_main "$@"
