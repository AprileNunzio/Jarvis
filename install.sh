#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for candidate in "$DIR/installer_wizard/bootstrap.sh" "$DIR/../installer_wizard/bootstrap.sh"; do
    [ -f "$candidate" ] && exec bash "$candidate" "$@"
done
exec bash <(curl -fsSL https://raw.githubusercontent.com/AprileNunzio/Jarvis/main/installer_wizard/bootstrap.sh) "$@"
