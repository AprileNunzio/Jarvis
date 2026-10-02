#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

PACKAGES=(libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui fonts-crosextra-carlito
          fonts-crosextra-caladea fonts-liberation2 fonts-dejavu-core fonts-noto-core)

VENV="$JARVIS_DIR/installer_wizard/venv"
REQ="$JARVIS_DIR/installer_wizard/features/documents/requirements.txt"

wanted() { [ "${JARVIS_DOCUMENTS:-1}" != "0" ]; }
python_ready() { "$VENV/bin/python" -c "import docx, openpyxl, pptx, matplotlib" >/dev/null 2>&1; }

step_check() {
    wanted || return 0
    command -v soffice >/dev/null 2>&1 && pkgs_present "${PACKAGES[@]}" && python_ready
}

step_apply() {
    if ! wanted; then
        progress 100 "Documenti Office disattivati"
        return 0
    fi
    progress 10 "Librerie Python per Word, Excel, PowerPoint e grafici"
    python_ready || retry 3 10 "$VENV/bin/pip" install -q -r "$REQ" || fail "Librerie dei documenti non installate"
    progress 30 "Installazione di LibreOffice (senza interfaccia grafica)"
    apt_install "${PACKAGES[@]}"
    progress 80 "Aggiornamento dei caratteri"
    fc-cache -f >/dev/null 2>&1 || true
    command -v soffice >/dev/null 2>&1 || fail "LibreOffice non risulta installato"
    info "LibreOffice $(soffice --version 2>/dev/null | head -1)"
    progress 100 "Documenti Office, LibreOffice e PDF pronti"
}

step_main "$@"
