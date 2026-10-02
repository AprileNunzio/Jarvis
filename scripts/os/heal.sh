#!/usr/bin/env bash
. "$(dirname "$0")/lib.sh"
set +e

step=${1:-generic}
info "Diagnosi e riparazione per lo step: $step"

case "$step" in
    system|gpu|security|maintenance|docker) need_apt=1 ;;
    *) need_apt=0 ;;
esac
if [ -n "$(dpkg --audit 2>/dev/null)" ]; then need_apt=1; fi
if [ "$need_apt" -eq 1 ] && ! pgrep -x apt-get >/dev/null && ! pgrep -x dpkg >/dev/null; then
    apt_heal
fi

free_mb=$(df -Pm / | awk 'NR==2 {print $4}')
if [ "${free_mb:-0}" -lt 4096 ]; then
    warn "Spazio disco basso (${free_mb} MB): pulizia"
    apt-get clean
    journalctl --vacuum-size=200M >/dev/null 2>&1
    command -v docker >/dev/null && docker system prune -f >/dev/null 2>&1
fi

if ! curl -fsS --max-time 8 -o /dev/null https://github.com; then
    warn "Rete non raggiungibile: riavvio risoluzione DNS"
    systemctl restart systemd-resolved >/dev/null 2>&1 || true
    sleep 5
fi

case "$step" in
    docker|core|services|gpu)
        if command -v docker >/dev/null && ! docker info >/dev/null 2>&1; then
            warn "Docker non risponde: riavvio"
            systemctl restart docker
            sleep 5
        fi
        ;;
    ollama|models|warmup)
        if systemctl list-unit-files ollama.service >/dev/null 2>&1; then
            warn "Riavvio del motore neurale"
            systemctl restart ollama
            sleep 5
        fi
        ;;
esac
info "Riparazione completata"
