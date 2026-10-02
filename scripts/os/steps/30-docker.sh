#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

daemon_json() {
    printf '%s\n' \
        '{' \
        '  "log-driver": "json-file",' \
        '  "log-opts": { "max-size": "20m", "max-file": "3" },' \
        '  "live-restore": true' \
        '}'
}

step_check() {
    command -v docker >/dev/null 2>&1 \
        && docker info >/dev/null 2>&1 \
        && docker compose version >/dev/null 2>&1 \
        && systemctl is-enabled docker >/dev/null 2>&1
}

step_apply() {
    if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
        progress 10 "Download Docker Engine"
        local installer
        installer=$(mktemp)
        retry 3 5 curl -fsSL https://get.docker.com -o "$installer"
        progress 30 "Installazione Docker Engine"
        retry 2 10 sh "$installer" || { apt_heal; sh "$installer"; }
        rm -f "$installer"
    fi

    progress 70 "Configurazione del demone Docker"
    local restart=0
    if [ -f /etc/docker/daemon.json ] && ! grep -q '"max-size"' /etc/docker/daemon.json; then
        warn "daemon.json personalizzato rilevato: lasciato invariato"
    elif daemon_json | write_if_changed /etc/docker/daemon.json; then
        restart=1
    fi

    systemctl enable docker containerd >/dev/null 2>&1 || true
    if [ "$restart" -eq 1 ] || ! docker info >/dev/null 2>&1; then
        progress 85 "Avvio Docker"
        systemctl restart docker
    fi
    wait_for 60 docker info || fail "Docker non risponde dopo il riavvio"
    info "$(docker --version)"
    progress 100 "Docker operativo"
}

step_main "$@"
