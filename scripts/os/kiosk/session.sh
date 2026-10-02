#!/usr/bin/env bash
URL="${JARVIS_KIOSK_URL:-http://127.0.0.1/}"
BASE="${URL%/}"
PROFILE="$HOME/.config/jarvis-chromium"
LOG="$HOME/.cache/jarvis-kiosk.log"
mkdir -p "$(dirname "$LOG")" "$PROFILE/Default"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] Avvio sessione kiosk su $URL"

xset s off s noblank -dpms
xsetroot -solid '#02040a' 2>/dev/null || true

openbox &
unclutter -idle 3 -root &

if pkill -u "$(id -u)" -f "user-data-dir=$PROFILE" 2>/dev/null; then
    echo "[$(date -Is)] Chiuso un Chromium rimasto da una sessione precedente"
    sleep 2
fi

for _ in $(seq 1 180); do
    curl -fs -o /dev/null --max-time 2 "$BASE/healthz" && break
    sleep 1
done

outputs() { xrandr --query 2>/dev/null | awk '/ connected/{print $1}'; }

arrange() {
    local prev="" out primary
    primary=$(xrandr --query 2>/dev/null | awk '/ connected primary/{print $1; exit}')
    for out in $primary $(outputs | grep -vx "${primary:-__none__}"); do
        if [ -z "$prev" ]; then xrandr --output "$out" --auto --primary --pos 0x0
        else xrandr --output "$out" --auto --right-of "$prev"; fi
        prev="$out"
    done
}

monitors() {
    xrandr --listmonitors 2>/dev/null | awk 'NR > 1 {
        split($3, a, /[\/x+]/); primary = ($2 ~ /\*/) ? 0 : 1
        print primary, a[5], a[6], a[1], a[3]
    }' | sort -k1,1n -k2,2n
}

signature() { xrandr --query 2>/dev/null | grep -E ' connected|\*' | md5sum | cut -c1-12; }

window() {
    local n="$1" x="$2" y="$3" w="$4" h="$5" url profile
    if [ "$n" -eq 0 ]; then url="$BASE/?x=$x"; profile="$PROFILE"
    else url="$BASE/screen?n=$n&x=$x"; profile="$PROFILE-screen$n"; fi
    mkdir -p "$profile/Default"
    rm -rf "$profile/Default/Sessions" "$profile/Default/Current Session" "$profile/Default/Current Tabs"         "$profile/Default/Last Session" "$profile/Default/Last Tabs" 2>/dev/null
    while true; do
        sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"[^"]*"/"exit_type":"Normal"/' \
            "$profile/Default/Preferences" 2>/dev/null || true
        chromium \
            --kiosk "$url" \
            --user-data-dir="$profile" \
            --window-position="$x,$y" \
            --window-size="$w,$h" \
            --no-first-run \
            --no-default-browser-check \
            --noerrdialogs \
            --disable-infobars \
            --disable-session-crashed-bubble \
            --lang=it \
            --disable-features=Translate,TranslateUI,MediaRouter,OverscrollHistoryNavigation \
            --disable-pinch \
            --overscroll-history-navigation=0 \
            --password-store=basic \
            --autoplay-policy=no-user-gesture-required \
            --use-fake-ui-for-media-stream \
            --enable-speech-dispatcher \
            --enable-gpu-rasterization \
            --ignore-gpu-blocklist \
            --check-for-update-interval=31536000
        echo "[$(date -Is)] Chromium dello schermo $n terminato (codice $?), riavvio tra 2s"
        sleep 2
    done
}

PIDS=()
start_all() {
    local n=0 primary x y w h
    arrange
    while read -r primary x y w h; do
        [ -n "$w" ] || continue
        echo "[$(date -Is)] Schermo $n: ${w}x${h} in ${x},${y}"
        window "$n" "$x" "$y" "$w" "$h" &
        PIDS+=("$!")
        n=$((n + 1))
    done < <(monitors)
    if [ "$n" -eq 0 ]; then
        window 0 0 0 1920 1080 &
        PIDS+=("$!")
    fi
}

stop_all() {
    local pid
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
    PIDS=()
    pkill -f "user-data-dir=$PROFILE" 2>/dev/null
    sleep 2
}

trap 'stop_all; exit 0' TERM INT
start_all
current=$(signature)
while true; do
    sleep 5
    next=$(signature)
    if [ "$next" != "$current" ]; then
        echo "[$(date -Is)] Monitor cambiati: riorganizzo le finestre"
        sleep 2
        stop_all
        start_all
        current=$(signature)
    fi
done
