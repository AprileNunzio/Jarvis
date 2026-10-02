#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

SOUP=/opt/jarvis-soup

soup_mode() {
    case "${JARVIS_STUDY_FINETUNE:-auto}" in
        1|0) echo "$JARVIS_STUDY_FINETUNE" ;;
        *) echo auto ;;
    esac
}
ram_ok() { [ "$(awk '/MemTotal/ {print int($2 / 1024 / 1024 + 0.5)}' /proc/meminfo)" -ge 8 ]; }
machine_capable() { has_usable_gpu && ram_ok; }

soup_wanted() {
    case "$(soup_mode)" in
        1) return 0 ;;
        0) return 1 ;;
        *) machine_capable ;;
    esac
}
soup_ready() { [ -x "$SOUP/venv/bin/soup" ] && "$SOUP/venv/bin/python" -c "import torch, peft, trl" 2>/dev/null; }

step_check() {
    soup_wanted || return 0
    soup_ready
}

step_apply() {
    if ! soup_wanted; then
        if [ "$(soup_mode)" = 0 ]; then
            progress 100 "Consolidamento nei pesi disattivato dall'utente"
        else
            progress 100 "Macchina non adatta all'addestramento: studio nella memoria a lungo termine (modificabile dal pannello)"
        fi
        return 0
    fi
    progress 10 "Ambiente Python per Soup"
    [ -x "$SOUP/venv/bin/python" ] || python3 -m venv "$SOUP/venv"
    retry 3 5 "$SOUP/venv/bin/pip" install -q --upgrade pip
    if ! has_usable_gpu; then
        warn "Soup forzato dall'utente senza GPU adatta: addestramento sulla CPU (molto lento)"
        progress 25 "PyTorch per CPU"
        retry 2 20 "$SOUP/venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu \
            || fail "Installazione di PyTorch per CPU non riuscita"
    fi
    progress 40 "Installazione di Soup (alcuni GB)"
    retry 2 20 "$SOUP/venv/bin/pip" install -q --prefer-binary "soup-cli[train]" \
        || fail "Installazione di Soup non riuscita"
    soup_ready || fail "Soup installato ma non funzionante"
    mkdir -p /var/lib/jarvis/study/soup
    progress 100 "Soup pronto per il consolidamento notturno"
}

step_main "$@"
