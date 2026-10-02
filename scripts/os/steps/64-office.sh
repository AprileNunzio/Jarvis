#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

PACKAGES=(libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui fonts-crosextra-carlito
          fonts-crosextra-caladea fonts-liberation2 fonts-dejavu-core fonts-noto-core)

wanted() { [ "${JARVIS_DOCUMENTS:-1}" != "0" ]; }

step_check() {
    wanted || return 0
    command -v soffice >/dev/null 2>&1 && pkgs_present "${PACKAGES[@]}"
}

step_apply() {
    if ! wanted; then
        progress 100 "Documenti Office disattivati"
        return 0
    fi
    progress 20 "Installazione di LibreOffice (senza interfaccia grafica)"
    apt_install "${PACKAGES[@]}"
    progress 80 "Aggiornamento dei caratteri"
    fc-cache -f >/dev/null 2>&1 || true
    command -v soffice >/dev/null 2>&1 || fail "LibreOffice non risulta installato"
    info "LibreOffice $(soffice --version 2>/dev/null | head -1)"
    progress 100 "Documenti Office, LibreOffice e PDF pronti"
}

step_main "$@"
