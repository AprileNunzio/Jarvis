#!/usr/bin/env bash
set -uo pipefail

JARVIS_DIR="${JARVIS_DIR:-/opt/Jarvis}"
STATE=/var/lib/jarvis
FAILURES="$STATE/supervisor_failures"
LOG=/var/log/jarvis/rollback.log
WINDOW=600
THRESHOLD=4
mkdir -p "$STATE" /var/log/jarvis
exec >>"$LOG" 2>&1

now=$(date +%s)
echo "$now" >> "$FAILURES"
recent=$(awk -v n="$now" -v w="$WINDOW" 'n - $1 < w' "$FAILURES" | wc -l)
awk -v n="$now" -v w="$WINDOW" 'n - $1 < w' "$FAILURES" > "$FAILURES.tmp" && mv "$FAILURES.tmp" "$FAILURES"
echo "[$(date -Is)] Fallimento del Supervisor ($recent negli ultimi $((WINDOW / 60)) minuti)"
[ "$recent" -lt "$THRESHOLD" ] && exit 0

good=$(cat "$STATE/last_good_rev" 2>/dev/null || true)
cd "$JARVIS_DIR" || exit 1
current=$(git -c safe.directory='*' rev-parse HEAD 2>/dev/null || true)

if [ -n "$good" ] && [ "$good" != "$current" ]; then
    echo "Crash-loop: rollback da $current a $good"
    echo "$current" >> "$STATE/bad_revs"
    git -c safe.directory='*' reset --hard "$good"
    rm -f "$STATE/update_pending.json"
else
    echo "Crash-loop senza versione precedente utilizzabile (current=$current good=$good)"
fi
: > "$FAILURES"
systemctl reset-failed jarvis-supervisor.service
systemctl start --no-block jarvis-supervisor.service
