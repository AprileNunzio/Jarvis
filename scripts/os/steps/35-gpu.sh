#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

step_check() {
    has_usable_gpu || return 0
    command -v nvidia-ctk >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi 'nvidia'
}

step_apply() {
    if ! has_usable_gpu; then
        progress 100 "Nessuna GPU NVIDIA utilizzabile: step non necessario"
        return 0
    fi
    progress 20 "Configurazione repository NVIDIA"
    retry 3 5 curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    retry 3 5 curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    progress 50 "Installazione NVIDIA Container Toolkit"
    apt_install nvidia-container-toolkit
    progress 85 "Registrazione runtime GPU in Docker"
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    wait_for 60 docker info || fail "Docker non risponde dopo la configurazione GPU"
    progress 100 "Accelerazione GPU attiva"
}

step_main "$@"
