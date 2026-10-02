#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

loaded() {
    curl -fsS --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null \
        | jq -e --arg m "$1" '.models[] | select(.name == $m or .model == $m)' >/dev/null
}

normalize() { case "$1" in *:*) echo "$1" ;; *) echo "$1:latest" ;; esac; }

present() {
    curl -fsS --max-time 10 "$OLLAMA_URL/api/tags" 2>/dev/null         | jq -e --arg m "$(normalize "$1")" '.models[] | select(.name == $m)' >/dev/null
}

primary_model() {
    local list="${JARVIS_LLM_CHAT_ORDER:-${JARVIS_LLM_FAST_MODEL:-${JARVIS_LLM_MODEL:-qwen2.5:3b}}},${JARVIS_LLM_DEEP_ORDER:-}"
    local m
    for m in ${list//,/ }; do
        case "$m" in cloud:*|"") continue ;; esac
        ollama_remote && ! present "$m" && continue
        echo "$m"; return
    done
}

ask() {
    curl -fsS --max-time 300 "$OLLAMA_URL/api/generate" \
        -d "{\"model\":\"$1\",\"prompt\":\"Rispondi solo: pronto\",\"stream\":false,\"keep_alive\":\"24h\",\"options\":{\"num_predict\":8}}" \
        | jq -r '.response' 2>/dev/null
}

unload_others() {
    local keep="$1" embed="$2" name
    ollama_remote && return 0
    for name in $(curl -fsS --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null | jq -r '.models[].name'); do
        [ "$name" = "$keep" ] || [ "$name" = "$embed" ] && continue
        curl -fsS --max-time 60 "$OLLAMA_URL/api/generate" -d "{\"model\":\"$name\",\"keep_alive\":0}" >/dev/null \
            && info "Scaricato dalla memoria $name (non è il cervello scelto)"
    done
}

step_check() {
    local main
    main=$(primary_model)
    [ -z "$main" ] || loaded "$(normalize "$main")"
}

step_apply() {
    local main embed reply
    main=$(primary_model)
    embed=$(normalize "${JARVIS_EMBED_MODEL:-nomic-embed-text}")

    progress 20 "Verifica rete di memoria semantica"
    if ollama_remote && ! present "$embed"; then
        warn "Il server Ollama remoto non ha $embed: la memoria semantica resta spenta finché non lo installi lì"
    else
        curl -fsS --max-time 120 "$OLLAMA_URL/api/embed" \
        -d "{\"model\":\"$embed\",\"input\":\"Jarvis online\",\"keep_alive\":\"5m\"}" >/dev/null \
        || fail "La rete di embedding $embed non risponde"
    fi

    if [ -z "$main" ]; then
        unload_others "" "$embed"
        progress 100 "Solo cervelli cloud: nessun modello locale tenuto in memoria"
        return
    fi
    main=$(normalize "$main")
    unload_others "$main" "$embed"
    progress 60 "Attivazione rete linguistica $main"
    reply=$(ask "$main") || fail "La rete linguistica $main non risponde"
    info "Test neurale: '$reply'"
    progress 100 "Rete linguistica $main attiva; gli altri modelli si caricano solo quando servono"
}

step_main "$@"
