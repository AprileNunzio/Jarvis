#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

STATE_FILE="$JARVIS_STATE/display-driver"
BLACKLIST=/etc/modprobe.d/jarvis-blacklist-nouveau.conf

mode() { echo "${JARVIS_GPU_DRIVER:-auto}"; }
state() { cut -d'|' -f1 "$STATE_FILE" 2>/dev/null || true; }
state_pkg() { cut -d'|' -f2 "$STATE_FILE" 2>/dev/null || true; }
set_state() { mkdir -p "$JARVIS_STATE"; echo "$1|${2:-}|${3:-}|$(date +%s)" > "$STATE_FILE"; }
nvidia_loaded() { lsmod 2>/dev/null | grep -q '^nvidia ' && command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; }
installed_pkg() { { dpkg-query -W -f='${Package} ${Status}\n' 'nvidia-*driver' 2>/dev/null || true; } | awk '/install ok installed/ {print $1; exit}'; }

enable_nonfree() {
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then
        if ! grep -qE '^Components:.*\bnon-free\b' /etc/apt/sources.list.d/debian.sources; then
            sed -i -E '/^Components:/ { /contrib/! s/$/ contrib/; /non-free( |$)/! s/$/ non-free/; /non-free-firmware/! s/$/ non-free-firmware/ }' \
                /etc/apt/sources.list.d/debian.sources
        fi
    elif [ -f /etc/apt/sources.list ]; then
        sed -i -E '/^deb .*debian/ { / contrib/! s/$/ contrib/; / non-free( |$)/! s/$/ non-free/; / non-free-firmware/! s/$/ non-free-firmware/ }' \
            /etc/apt/sources.list
    fi
    retry 3 10 apt-get update -q
}

recommended() {
    apt_install nvidia-detect >/dev/null 2>&1 || return 1
    { nvidia-detect 2>/dev/null || true; } | { grep -oE '^ *nvidia-[a-z0-9.-]*driver' || true; } | tr -d ' ' | sed -n 1p
}

secure_boot() { command -v mokutil >/dev/null 2>&1 && mokutil --sb-state 2>/dev/null | grep -qi 'enabled'; }

schedule_reboot() {
    if [ "${JARVIS_GPU_DRIVER_REBOOT:-night}" = "now" ]; then
        shutdown -r +2 "Jarvis: attivazione del driver video NVIDIA" || true
        detail "Riavvio tra 2 minuti per attivare il driver"
    else
        shutdown -r 04:15 "Jarvis: attivazione del driver video NVIDIA" || true
        detail "Riavvio programmato alle 04:15 per attivare il driver"
    fi
}

revert() {
    local why=${1:-verifica non superata} pkg
    pkg=$(state_pkg)
    [ -n "$pkg" ] || pkg=$(installed_pkg)
    info "Ritorno al driver nouveau: $why"
    [ -n "$pkg" ] && apt-get purge -y -q "$pkg" nvidia-detect >/dev/null 2>&1
    apt-get autoremove -y -q >/dev/null 2>&1
    rm -f "$BLACKLIST"
    update-initramfs -u >/dev/null 2>&1 || true
    set_state failed "$pkg" "$why"
    shutdown -r +1 "Jarvis: ripristino del driver video precedente" || true
}

step_check() {
    has_nvidia_gpu || return 0
    case "$(mode)" in
        nouveau) [ -z "$(installed_pkg)" ] ;;
        *)
            case "$(state)" in
                failed|none|pending-reboot|verify) return 0 ;;
            esac
            nvidia_loaded
            ;;
    esac
}

step_apply() {
    if ! has_nvidia_gpu; then
        progress 100 "Nessuna scheda NVIDIA: step non necessario"
        return 0
    fi
    if [ "$(mode)" = "nouveau" ]; then
        progress 50 "Rimozione del driver NVIDIA come richiesto"
        revert "scelto nelle impostazioni"
        set_state none "" "driver libero scelto nelle impostazioni"
        progress 100 "Driver libero nouveau ripristinato (riavvio tra un minuto)"
        return 0
    fi
    if nvidia_loaded; then
        set_state ok "$(installed_pkg)"
        progress 100 "Driver NVIDIA già attivo"
        return 0
    fi
    if secure_boot; then
        set_state none "" "Secure Boot attivo: il driver non firmato non si caricherebbe"
        progress 100 "Secure Boot attivo: resto sul driver libero"
        return 0
    fi
    progress 15 "Abilitazione dei pacchetti non liberi di Debian"
    enable_nonfree || { set_state none "" "repository non raggiungibili"; progress 100 "Repository non raggiungibili: riprovo più avanti"; return 0; }
    progress 30 "Ricerca del driver adatto alla scheda"
    local pkg
    pkg=$(recommended || true)
    if [ -z "$pkg" ]; then
        set_state none "" "nessun driver ufficiale per questa scheda"
        progress 100 "Nessun driver ufficiale adatto: resto sul driver libero"
        return 0
    fi
    progress 45 "Installazione di $pkg (compilazione del modulo, alcuni minuti)"
    if ! apt_install "linux-headers-$(uname -r)" "$pkg"; then
        apt-get purge -y -q "$pkg" >/dev/null 2>&1
        set_state failed "$pkg" "installazione non riuscita"
        progress 100 "Installazione del driver non riuscita: resto sul driver libero"
        return 0
    fi
    printf 'blacklist nouveau\noptions nouveau modeset=0\n' > "$BLACKLIST"
    update-initramfs -u >/dev/null 2>&1 || true
    set_state pending-reboot "$pkg" "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
    progress 90 "Driver $pkg installato"
    schedule_reboot
    progress 100 "Driver $pkg installato: attivo dopo il riavvio, con ritorno automatico se qualcosa non va"
}

if [ "${1:-}" = "revert" ]; then
    revert "${2:-verifica non superata}"
    exit 0
fi
step_main "$@"
