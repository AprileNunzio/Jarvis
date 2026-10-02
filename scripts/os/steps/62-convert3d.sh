#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

free_gb() { df -Pk / | awk 'NR == 2 {printf "%d", $4 / 1024 / 1024}'; }
ram_gb() { awk '/MemTotal/ {printf "%d", ($2 / 1024 / 1024) + 0.5}' /proc/meminfo; }

wanted() {
    case "${JARVIS_3D_CONVERT:-auto}" in
        0) return 1 ;;
        1) return 0 ;;
        *) [ "$(free_gb)" -ge 20 ] && [ "$(ram_gb)" -ge 4 ] ;;
    esac
}

have_blender() { command -v blender >/dev/null 2>&1; }
have_dwg() { command -v dwg2dxf >/dev/null 2>&1; }
dwg_packaged() { apt-cache show libredwg-utils >/dev/null 2>&1 || apt-cache show libredwg-tools >/dev/null 2>&1; }

step_check() {
    wanted || return 0
    have_blender && { have_dwg || ! dwg_packaged; }
}

step_apply() {
    if ! wanted; then
        progress 100 "Conversione 3D non installata (disattivata o spazio insufficiente)"
        return 0
    fi
    progress 20 "Installazione di Blender per aprire BLEND e USD/USDZ"
    retry 2 10 apt-get install -y -q --no-install-recommends blender || warn "Blender non installato"
    progress 70 "Installazione di LibreDWG per aprire i DWG"
    if dwg_packaged; then
        apt-get install -y -q libredwg-utils 2>/dev/null || apt-get install -y -q libredwg-tools 2>/dev/null \
            || warn "LibreDWG non installato"
    else
        info "LibreDWG non è nei repository di questa distribuzione: i DWG restano da convertire in DXF"
    fi
    have_blender && info "Blender: $(blender --version 2>/dev/null | head -n 1)"
    have_dwg && info "LibreDWG: dwg2dxf disponibile"
    progress 100 "Conversione 3D pronta"
}

step_main "$@"
