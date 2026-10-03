#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

FC_VERSION=v1.10.1
FC_DIR=/var/lib/jarvis/firecracker
FC_BIN=/usr/local/bin/firecracker
FC_URL="https://github.com/firecracker-microvm/firecracker/releases/download/$FC_VERSION/firecracker-$FC_VERSION-x86_64.tgz"
FC_SHA256=36112969952b0e34fadcfca769d48a55dc22cbba99af17e02bd0e24fc35adc77
KERNEL_URL=https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/vmlinux-6.1.102
KERNEL_SHA256=49ba99a5299444ac59dda2efc3569cc2d58a5d72ea6475a6bfc37aa0bf322e54
IMAGE=jarvis-sandbox:local
STATUS_FILE="$FC_DIR/status"
TRIED_FILE="$JARVIS_STATE/.firecracker-tried"
RETRY_AFTER_SECONDS=21600

sources() {
    find "$JARVIS_DIR/sandbox_broker/microvm" -name '*.py' | sort
    echo "$JARVIS_DIR/scripts/os/steps/36-firecracker.sh"
    echo "$JARVIS_DIR/docker/sandbox/Dockerfile"
}

mark_status() {
    mkdir -p "$FC_DIR"
    echo "$1" > "$STATUS_FILE"
}

unsupported_reason() {
    [ "$(uname -m)" = x86_64 ] || { echo "architettura non supportata"; return 0; }
    [ -c /dev/kvm ] || { echo "virtualizzazione hardware (KVM) assente"; return 0; }
    [ -r /dev/kvm ] && [ -w /dev/kvm ] || { echo "KVM non accessibile"; return 0; }
    return 1
}

tried_recently() {
    [ -f "$TRIED_FILE" ]         && [ "$(cat "$TRIED_FILE")" = "$(_code_hash $(sources))" ]         && [ $(( $(date +%s) - $(stat -c %Y "$TRIED_FILE") )) -lt "$RETRY_AFTER_SECONDS" ]
}

assets_ready() {
    [ -x "$FC_BIN" ] && [ -f "$FC_DIR/vmlinux" ] && [ -f "$FC_DIR/rootfs.ext4" ] && code_current firecracker $(sources)
}

step_check() {
    local reason
    if reason=$(unsupported_reason); then
        mark_status "non disponibile: $reason"
        return 0
    fi
    assets_ready && return 0
    tried_recently
}

fetch_verified() {
    local url=$1 sha=$2 target=$3
    retry 4 15 curl -fsSL --connect-timeout 20 -C - -o "$target" "$url" || return 1
    echo "$sha  $target" | sha256sum -c >/dev/null 2>&1
}

install_firecracker() {
    local tmp
    tmp=$(mktemp -d)
    fetch_verified "$FC_URL" "$FC_SHA256" "$tmp/fc.tgz" || { rm -rf "$tmp"; return 1; }
    tar -xzf "$tmp/fc.tgz" -C "$tmp"
    install -m 0755 "$tmp/release-$FC_VERSION-x86_64/firecracker-$FC_VERSION-x86_64" "$FC_BIN"
    rm -rf "$tmp"
}

install_kernel() {
    mkdir -p "$FC_DIR"
    fetch_verified "$KERNEL_URL" "$KERNEL_SHA256" "$FC_DIR/vmlinux.part" || { rm -f "$FC_DIR/vmlinux.part"; return 1; }
    mv -f "$FC_DIR/vmlinux.part" "$FC_DIR/vmlinux"
}

build_rootfs() {
    local tmp tree cid size_mb
    tmp=$(mktemp -d)
    tree="$tmp/tree"
    mkdir -p "$tree"
    cid=$(docker create "$IMAGE") || { rm -rf "$tmp"; return 1; }
    docker export "$cid" | tar -x -C "$tree"
    docker rm "$cid" >/dev/null
    mkdir -p "$tree/proc" "$tree/sys" "$tree/dev" "$tree/tmp" "$tree/in" "$tree/out" "$tree/sbin"
    install -m 0755 "$JARVIS_DIR/sandbox_broker/microvm/guest_init.py" "$tree/sbin/jarvis-init"
    size_mb=$(( $(du -sm "$tree" | cut -f1) + 64 ))
    mke2fs -q -t ext4 -O ^has_journal -L jarvisroot -d "$tree" "$tmp/rootfs.ext4" "${size_mb}M" || { rm -rf "$tmp"; return 1; }
    mv -f "$tmp/rootfs.ext4" "$FC_DIR/rootfs.ext4"
    chmod 0644 "$FC_DIR/rootfs.ext4" "$FC_DIR/vmlinux"
    rm -rf "$tmp"
}

step_apply() {
    local reason
    mkdir -p "$JARVIS_STATE" "$FC_DIR"
    _code_hash $(sources) > "$TRIED_FILE"
    if reason=$(unsupported_reason); then
        mark_status "non disponibile: $reason"
        exit 0
    fi
    docker image inspect "$IMAGE" >/dev/null 2>&1 || { warn "Immagine sandbox non ancora pronta: riprovo più tardi"; exit 0; }
    progress 10 "Download di Firecracker"
    if [ ! -x "$FC_BIN" ] && ! install_firecracker; then
        mark_status "non disponibile: download di Firecracker non riuscito"
        warn "Firecracker non scaricabile ora: la sandbox resta su gVisor o sul container rinforzato"
        exit 0
    fi
    progress 40 "Kernel della micro-VM"
    if [ ! -f "$FC_DIR/vmlinux" ] && ! install_kernel; then
        mark_status "non disponibile: kernel non scaricabile"
        warn "Kernel per Firecracker non scaricabile ora"
        exit 0
    fi
    progress 60 "Immagine di sistema della micro-VM"
    command -v mke2fs >/dev/null 2>&1 || apt_install e2fsprogs util-linux || true
    if ! build_rootfs; then
        mark_status "non disponibile: immagine di sistema non costruita"
        warn "Immagine della micro-VM non costruita: la sandbox resta su gVisor o sul container rinforzato"
        exit 0
    fi
    progress 90 "Attivazione"
    code_mark firecracker $(sources)
    mark_status "pronta: Firecracker $FC_VERSION"
    systemctl restart jarvis-sandbox || warn "Broker non riavviato: userà Firecracker al prossimo controllo"
    progress 100 "Firecracker pronto"
}

step_main "$@"
