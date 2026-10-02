#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

MUSIC=/opt/jarvis-music

music_enabled() { [ "${JARVIS_MUSIC_ID:-1}" != "0" ] && [ "${JARVIS_EAR:-1}" != "0" ]; }
music_ready() { "$MUSIC/venv/bin/python" -c "import shazamio" 2>/dev/null; }

step_check() {
    music_enabled || return 0
    music_ready
}

step_apply() {
    if ! music_enabled; then
        progress 100 "Riconoscimento musicale disattivato"
        return 0
    fi
    progress 20 "Ambiente per il riconoscimento musicale"
    [ -x "$MUSIC/venv/bin/python" ] || python3 -m venv "$MUSIC/venv"
    retry 3 5 "$MUSIC/venv/bin/pip" install -q --upgrade pip
    progress 50 "Installazione del riconoscimento dei brani"
    retry 3 10 "$MUSIC/venv/bin/pip" install -q --prefer-binary --upgrade shazamio "audioop-lts; python_version >= '3.13'" \
        || fail "Libreria di riconoscimento musicale non installata"
    if ! music_ready; then
        warn "Import non riuscito:"
        "$MUSIC/venv/bin/python" -c "import shazamio" 2>&1 | tail -n 5
        fail "Riconoscimento musicale non funzionante"
    fi
    progress 100 "Riconoscimento musicale pronto"
}

step_main "$@"
