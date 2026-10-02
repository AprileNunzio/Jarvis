#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

SYSCTL_FILE=/etc/sysctl.d/99-jarvis-hardening.conf
PORTS_TCP=(22 80 8080 8443)
PORTS_UDP=(51820 50505)

sysctl_conf() {
    printf '%s\n' \
        '# Gestito da Jarvis OS — non modificare manualmente' \
        'fs.protected_fifos = 2' \
        'fs.protected_regular = 2' \
        'fs.suid_dumpable = 0' \
        'kernel.kptr_restrict = 2' \
        'kernel.sysrq = 0' \
        'kernel.unprivileged_bpf_disabled = 1' \
        'net.ipv4.conf.all.accept_redirects = 0' \
        'net.ipv4.conf.all.log_martians = 1' \
        'net.ipv4.conf.all.rp_filter = 1' \
        'net.ipv4.conf.all.send_redirects = 0' \
        'net.ipv4.conf.default.accept_redirects = 0' \
        'net.ipv4.conf.default.accept_source_route = 0' \
        'net.ipv4.tcp_syncookies = 1' \
        'net.ipv6.conf.all.accept_redirects = 0' \
        'net.ipv6.conf.default.accept_redirects = 0'
}

step_check() {
    sysctl_conf | same_content "$SYSCTL_FILE" || return 1
    command -v ufw >/dev/null 2>&1 || return 1
    local status p
    status=$(ufw status 2>/dev/null)
    echo "$status" | grep -q "Status: active" || return 1
    for p in "${PORTS_TCP[@]}"; do echo "$status" | grep -qE "^${p}/tcp +ALLOW" || return 1; done
    for p in "${PORTS_UDP[@]}"; do echo "$status" | grep -qE "^${p}/udp +ALLOW" || return 1; done
}

step_apply() {
    progress 20 "Hardening del kernel"
    sysctl_conf | write_if_changed "$SYSCTL_FILE" || true
    sysctl --system >/dev/null 2>&1 || warn "Alcuni parametri sysctl non sono supportati da questo kernel"

    progress 50 "Configurazione firewall"
    apt_install ufw
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    local p
    for p in "${PORTS_TCP[@]}"; do ufw allow "${p}/tcp" >/dev/null; done
    for p in "${PORTS_UDP[@]}"; do ufw allow "${p}/udp" >/dev/null; done
    progress 80 "Attivazione firewall"
    ufw --force enable >/dev/null
    info "Porte aperte: TCP ${PORTS_TCP[*]} — UDP ${PORTS_UDP[*]}"
    progress 100 "Sistema protetto"
}

step_main "$@"
