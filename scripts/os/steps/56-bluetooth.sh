#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

BT_PKGS=(bluez pulseaudio-module-bluetooth)

bt_enabled() { [ "${JARVIS_BLUETOOTH:-1}" != "0" ]; }
bt_adapter() { compgen -G "/sys/class/bluetooth/hci*" >/dev/null; }

kiosk_pactl() {
    local uid
    uid=$(id -u "$JARVIS_KIOSK_USER" 2>/dev/null) || return 1
    runuser -u "$JARVIS_KIOSK_USER" -- env "XDG_RUNTIME_DIR=/run/user/$uid" pactl "$@"
}

pulse_ready() {
    kiosk_pactl list short modules 2>/dev/null | grep -q module-bluetooth-discover
}

step_check() {
    bt_enabled || return 0
    bt_adapter || return 0
    pkgs_present "${BT_PKGS[@]}" || return 1
    systemctl is-active --quiet bluetooth || return 1
    id -nG "$JARVIS_KIOSK_USER" 2>/dev/null | grep -qw bluetooth || return 1
    ! id "$JARVIS_KIOSK_USER" >/dev/null 2>&1 || pulse_ready
}

step_apply() {
    if ! bt_enabled; then
        progress 100 "Bluetooth disattivato"
        return 0
    fi
    if ! bt_adapter; then
        progress 100 "Nessun adattatore Bluetooth: collega una chiavetta USB e Jarvis la configurerà"
        return 0
    fi
    progress 20 "Installazione di BlueZ e del supporto audio Bluetooth"
    apt_install "${BT_PKGS[@]}" || fail "Pacchetti Bluetooth non installati"
    progress 50 "Attivazione dell'adattatore"
    mkdir -p /etc/bluetooth
    if [ -f /etc/bluetooth/main.conf ] && ! grep -q '^AutoEnable=true' /etc/bluetooth/main.conf; then
        if grep -q '^\[Policy\]' /etc/bluetooth/main.conf; then
            sed -i '/^\[Policy\]/a AutoEnable=true' /etc/bluetooth/main.conf
        else
            printf '\n[Policy]\nAutoEnable=true\n' >> /etc/bluetooth/main.conf
        fi
    fi
    rfkill unblock bluetooth 2>/dev/null || true
    systemctl enable --now bluetooth || fail "Servizio Bluetooth non avviato"
    wait_for 20 bluetoothctl show || fail "Adattatore Bluetooth non risponde"
    bluetoothctl power on >/dev/null || warn "Accensione dell'adattatore non confermata"
    progress 75 "Permessi per il display"
    getent group bluetooth >/dev/null || groupadd --system bluetooth
    if id "$JARVIS_KIOSK_USER" >/dev/null 2>&1; then
        usermod -aG bluetooth "$JARVIS_KIOSK_USER"
        progress 85 "Collegamento dell'audio Bluetooth"
        pulse_ready || kiosk_pactl load-module module-bluetooth-policy >/dev/null 2>&1 || true
        pulse_ready || kiosk_pactl load-module module-bluetooth-discover >/dev/null \
            || warn "Il modulo audio Bluetooth sarà attivo al prossimo avvio del display"
    fi
    progress 100 "Bluetooth pronto"
}

step_main "$@"
