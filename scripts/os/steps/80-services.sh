#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

core_healthy() { curl -fsS --max-time 5 "$CORE_URL/health" >/dev/null 2>&1; }

running() {
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]
}

up_to_date() {
    local service=$1 want_hash have_hash
    want_hash=$(JARVIS_SRC_HASH=$(core_src_hash) compose config --hash "$service" 2>/dev/null | awk '{print $2}')
    have_hash=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.config-hash" }}' "$service" 2>/dev/null)
    [ -n "$want_hash" ] && [ "$want_hash" = "$have_hash" ] || return 1
    if [ "$service" = jarvis-core ]; then
        [ "$(docker inspect -f '{{.Image}}' jarvis-core 2>/dev/null)" = \
          "$(docker image inspect -f '{{.Id}}' jarvis-core:local 2>/dev/null)" ] || return 1
    fi
}

step_check() {
    running jarvis-core && running jarvis-qdrant \
        && up_to_date jarvis-core && up_to_date jarvis-qdrant \
        && core_healthy
}

remove_foreign_containers() {
    local c project
    for c in jarvis-core jarvis-qdrant jarvis-inference; do
        project=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$c" 2>/dev/null || true)
        if [ -n "$project" ] && [ "$project" != "jarvis" ]; then
            warn "Rimozione container legacy $c (progetto '$project')"
            docker rm -f "$c" >/dev/null 2>&1 || true
        fi
    done
}

step_apply() {
    progress 10 "Pulizia configurazioni precedenti"
    remove_foreign_containers
    [ -d /etc/timezone ] && rmdir /etc/timezone 2>/dev/null || true
    mkdir -p "$JARVIS_DIR/data/db" "$JARVIS_DIR/data/certs" "$JARVIS_DIR/data/qdrant" "$JARVIS_DIR/data/models"

    progress 30 "Avvio servizi container"
    export JARVIS_SRC_HASH
    JARVIS_SRC_HASH=$(core_src_hash)
    retry 3 5 compose up -d --remove-orphans --no-build jarvis-qdrant jarvis-core
    if [[ ",${COMPOSE_PROFILES:-}," == *",gpu,"* ]]; then
        if docker image inspect jarvis-inference:local >/dev/null 2>&1; then
            compose up -d --no-build jarvis-inference || warn "Inferenza GPU non avviata: Jarvis prosegue su CPU"
        else
            warn "Immagine di inferenza GPU assente: servizio opzionale saltato"
        fi
    else
        docker rm -f jarvis-inference >/dev/null 2>&1 || true
    fi

    progress 60 "Attesa risposta di Jarvis Core"
    if ! wait_for 180 core_healthy; then
        warn "Jarvis Core non risponde: ultimi log"
        docker logs --tail 40 jarvis-core 2>&1 || true
        fail "Jarvis Core non risponde su $CORE_URL/health"
    fi
    info "$(curl -fsS "$CORE_URL/health" | jq -c '{status, version, active_agents}' 2>/dev/null)"
    progress 100 "Servizi operativi"
}

step_main "$@"
