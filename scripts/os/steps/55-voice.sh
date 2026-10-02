#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

VOICE_DIR=/opt/jarvis-voice
KOKORO="$VOICE_DIR/kokoro"
KOKORO_URL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
PIPER_VERSION=2023.11.14-2
VOICES_URL=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0
FALLBACK="${JARVIS_VOICE_FALLBACK:-it_IT-riccardo-x_low}"
UNIT_SRC="$JARVIS_DIR/scripts/os/systemd/jarvis-voice.service"
UNIT=/etc/systemd/system/jarvis-voice.service
CODE="$JARVIS_DIR/installer_wizard/features/voices/service.py"
MIGRATION="$JARVIS_STATE/.voice-v2"

piper_arch() {
    case "$(uname -m)" in
        x86_64) echo x86_64 ;;
        aarch64) echo aarch64 ;;
        *) fail "Architettura non supportata da Piper: $(uname -m)" ;;
    esac
}

piper_voice_path() {
    local v=$1 lang=${1%%-*} rest=${1#*-}
    echo "${lang%%_*}/$lang/${rest%-*}/${rest##*-}/$v"
}

kokoro_ok() { curl -fsS --max-time 5 http://127.0.0.1:8092/health >/dev/null 2>&1; }

piper_ok() {
    local out size
    out=$(mktemp)
    echo "Sistemi vocali operativi." \
        | "$VOICE_DIR/piper/piper" --model "$VOICE_DIR/voices/$FALLBACK.onnx" --output_raw >"$out" 2>/dev/null || true
    size=$(stat -c %s "$out")
    rm -f "$out"
    [ "$size" -gt 4096 ]
}

step_check() {
    [ -f "$MIGRATION" ] || return 1
    [ -x "$VOICE_DIR/piper/piper" ] && [ -s "$VOICE_DIR/voices/$FALLBACK.onnx" ] || return 1
    [ -s "$KOKORO/kokoro-v1.0.onnx" ] && [ -s "$KOKORO/voices-v1.0.bin" ] || return 1
    same_content "$UNIT" < "$UNIT_SRC" && systemctl is-enabled --quiet jarvis-voice && kokoro_ok \
        && code_current voice "$CODE"
}

step_apply() {
    mkdir -p "$VOICE_DIR/voices" "$KOKORO"

    if [ ! -x "$VOICE_DIR/piper/piper" ]; then
        progress 5 "Download del motore vocale di riserva"
        local tarball
        tarball=$(mktemp)
        retry 3 5 curl -fsSL -o "$tarball" \
            "https://github.com/rhasspy/piper/releases/download/$PIPER_VERSION/piper_linux_$(piper_arch).tar.gz"
        rm -rf "$VOICE_DIR/piper"
        tar -xzf "$tarball" -C "$VOICE_DIR"
        rm -f "$tarball"
    fi
    local ext
    for ext in onnx onnx.json; do
        if [ ! -s "$VOICE_DIR/voices/$FALLBACK.$ext" ]; then
            retry 3 5 curl -fsSL -o "$VOICE_DIR/voices/$FALLBACK.$ext.part" "$VOICES_URL/$(piper_voice_path "$FALLBACK").$ext"
            mv -f "$VOICE_DIR/voices/$FALLBACK.$ext.part" "$VOICE_DIR/voices/$FALLBACK.$ext"
        fi
    done
    piper_ok || warn "Voce di riserva Piper non funzionante"

    progress 25 "Ambiente della voce neurale"
    [ -x "$KOKORO/venv/bin/python" ] || python3 -m venv "$KOKORO/venv"
    if ! "$KOKORO/venv/bin/python" -c "import kokoro_onnx, numpy" 2>/dev/null; then
        retry 3 5 "$KOKORO/venv/bin/pip" install -q --upgrade pip
        retry 3 5 "$KOKORO/venv/bin/pip" install -q kokoro-onnx
    fi
    local f
    for f in kokoro-v1.0.onnx voices-v1.0.bin; do
        if [ ! -s "$KOKORO/$f" ]; then
            progress 45 "Download della voce neurale maschile ($f)"
            retry 3 5 curl -fsSL -o "$KOKORO/$f.part" "$KOKORO_URL/$f"
            mv -f "$KOKORO/$f.part" "$KOKORO/$f"
        fi
    done

    progress 80 "Avvio del servizio vocale"
    if write_if_changed "$UNIT" < "$UNIT_SRC"; then systemctl daemon-reload; fi
    systemctl enable jarvis-voice >/dev/null 2>&1
    systemctl restart jarvis-voice
    wait_for 90 kokoro_ok || fail "Il servizio vocale Kokoro non risponde"
    code_mark voice "$CODE"

    if [ ! -f "$MIGRATION" ]; then
        set_env JARVIS_VOICE im_nicola
        touch "$MIGRATION"
    fi
    info "Voce neurale: ${JARVIS_VOICE:-im_nicola} (riserva: $FALLBACK)"
    progress 100 "Voce neurale maschile attiva"
}

step_main "$@"
