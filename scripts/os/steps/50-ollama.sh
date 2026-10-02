#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

OVERRIDE=/etc/systemd/system/ollama.service.d/jarvis.conf

max_loaded() {
    local ram_gb
    ram_gb=$(awk '/MemTotal/ {printf "%d", ($2 / 1024 / 1024) + 0.5}' /proc/meminfo)
    if [ "$ram_gb" -ge 6 ]; then echo 3; else echo 2; fi
}

override_conf() {
    printf '%s\n' \
        '# Gestito da Jarvis OS' \
        '[Service]' \
        'Environment="OLLAMA_HOST=127.0.0.1:11434"' \
        'Environment="OLLAMA_KEEP_ALIVE=24h"' \
        "Environment=\"OLLAMA_MAX_LOADED_MODELS=$(max_loaded)\"" \
        'Environment="OLLAMA_NUM_PARALLEL=1"' \
        'Restart=always' \
        'RestartSec=3' \
        '# priorità bassa: ascolto e voce vengono prima del "pensiero" del modello' \
        'CPUWeight=40' \
        'Nice=5'
}

api_ok() { curl -fsS --max-time 5 "$OLLAMA_URL/api/version" >/dev/null 2>&1; }

local_off() { ! systemctl is-active --quiet ollama 2>/dev/null; }

step_check() {
    if ollama_remote; then
        api_ok && local_off
        return
    fi
    command -v ollama >/dev/null 2>&1 \
        && override_conf | same_content "$OVERRIDE" \
        && systemctl is-enabled ollama >/dev/null 2>&1 \
        && api_ok
}

step_apply() {
    if ollama_remote; then
        progress 30 "Motore neurale remoto: $OLLAMA_URL"
        if systemctl is-active --quiet ollama 2>/dev/null; then
            systemctl disable --now ollama >/dev/null 2>&1 || true
            info "Ollama locale fermato: uso il server remoto e libero la memoria"
        fi
        wait_for 30 api_ok || fail "Il server Ollama remoto $OLLAMA_URL non risponde (sul server remoto serve OLLAMA_HOST=0.0.0.0)"
        info "Ollama remoto $(curl -fsS "$OLLAMA_URL/api/version" | jq -r .version 2>/dev/null) operativo su $OLLAMA_URL"
        progress 100 "Motore neurale remoto operativo"
        return
    fi
    if ! command -v ollama >/dev/null 2>&1; then
        progress 10 "Download del motore neurale Ollama"
        local installer
        installer=$(mktemp)
        retry 3 5 curl -fsSL https://ollama.com/install.sh -o "$installer"
        progress 25 "Installazione Ollama (può richiedere alcuni minuti)"
        retry 2 10 sh "$installer"
        rm -f "$installer"
    fi

    progress 75 "Configurazione servizio neurale"
    if override_conf | write_if_changed "$OVERRIDE"; then
        systemctl daemon-reload
    fi
    systemctl enable ollama >/dev/null 2>&1
    systemctl restart ollama

    progress 90 "Attesa risposta del motore neurale"
    wait_for 90 api_ok || fail "Ollama non risponde su $OLLAMA_URL"
    info "Ollama $(curl -fsS "$OLLAMA_URL/api/version" | jq -r .version 2>/dev/null) operativo"
    progress 100 "Motore neurale operativo"
}

step_main "$@"
