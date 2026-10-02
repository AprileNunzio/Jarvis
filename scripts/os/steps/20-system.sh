#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

PACKAGES=(
    ca-certificates curl gnupg git jq zstd pciutils lsb-release ufw
    python3 python3-venv python3-pip
    xserver-xorg x11-xserver-utils xinit openbox chromium unclutter
    fonts-dejavu-core fonts-noto-color-emoji
    alsa-utils pulseaudio speech-dispatcher espeak-ng ffmpeg
    nmap avahi-daemon avahi-utils
    unattended-upgrades apt-listchanges
)

step_check() { pkgs_present "${PACKAGES[@]}"; }

step_apply() {
    progress 5 "Riparazione preventiva del gestore pacchetti"
    dpkg --configure -a || true
    progress 15 "Aggiornamento indici dei pacchetti"
    retry 3 5 apt-get update -q || { apt_heal; apt-get update -q; }

    local p i=0 missing=()
    for p in "${PACKAGES[@]}"; do pkgs_present "$p" || missing+=("$p"); done
    if [ ${#missing[@]} -eq 0 ]; then
        progress 100 "Tutti i pacchetti sono presenti"
        return 0
    fi
    info "Da installare (${#missing[@]}): ${missing[*]}"
    for p in "${missing[@]}"; do
        i=$((i + 1))
        progress $((20 + i * 78 / ${#missing[@]})) "Installazione $p ($i/${#missing[@]})"
        detail "$p"
        if ! retry 2 5 apt-get install -y -q --no-install-recommends "$p"; then
            apt_heal
            apt-get install -y -q --no-install-recommends "$p" || warn "Pacchetto non installato: $p"
        fi
    done
    progress 100 "Pacchetti di sistema installati"
}

step_main "$@"
