#!/usr/bin/env bash
. "$(dirname "$0")/../lib.sh"

models() {
    printf '%s\n' "${JARVIS_LLM_MODEL:-qwen2.5:3b}" "${JARVIS_LLM_FAST_MODEL:-${JARVIS_LLM_MODEL:-qwen2.5:3b}}" \
        "${JARVIS_EMBED_MODEL:-nomic-embed-text}" | awk '!seen[$0]++'
}

normalize() { case "$1" in *:*) echo "$1" ;; *) echo "$1:latest" ;; esac; }

model_present() {
    curl -fsS --max-time 10 "$OLLAMA_URL/api/tags" 2>/dev/null \
        | jq -e --arg m "$(normalize "$1")" '.models[] | select(.name == $m)' >/dev/null
}

step_check() {
    local m
    ollama_remote && return 0
    for m in $(models); do model_present "$m" || return 1; done
}

pull_model() {
    local model=$1 base=$2 span=$3
    python3 - "$OLLAMA_URL" "$model" "$base" "$span" <<'PY'
import json, sys, time, urllib.request

url, model, base, span = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
req = urllib.request.Request(
    f"{url}/api/pull",
    data=json.dumps({"model": model, "stream": True}).encode(),
    headers={"Content-Type": "application/json"},
)
last_emit, last_bytes, last_t = 0.0, 0, time.time()
with urllib.request.urlopen(req, timeout=3600) as resp:
    for raw in resp:
        msg = json.loads(raw.decode() or "{}")
        if "error" in msg:
            print(f"[FAIL] {msg['error']}", flush=True)
            sys.exit(1)
        status = msg.get("status", "")
        total, done = msg.get("total") or 0, msg.get("completed") or 0
        now = time.time()
        if total and now - last_emit >= 1.0:
            speed = max(0, (done - last_bytes) / max(now - last_t, 0.001))
            eta = int((total - done) / speed) if speed > 0 else 0
            pct = done * 100 // total
            print(f"@@PROGRESS {base + pct * span // 100} Download {model}: {pct}%", flush=True)
            print(f"@@DETAIL {model} — {done / 1e9:.2f}/{total / 1e9:.2f} GB — "
                  f"{speed / 1e6:.1f} MB/s — ETA {eta // 60}m{eta % 60:02d}s", flush=True)
            last_emit, last_bytes, last_t = now, done, now
        elif not total and status:
            print(f"[INFO] {model}: {status}", flush=True)
PY
}

step_apply() {
    curl -fsS --max-time 5 "$OLLAMA_URL/api/version" >/dev/null || fail "Ollama non è in esecuzione"
    local all=($(models)) i=0 n span
    n=${#all[@]}
    span=$((100 / n))
    for m in "${all[@]}"; do
        if model_present "$m"; then
            info "Rete neurale già presente: $m"
        else
            info "Download rete neurale: $m"
            retry 3 10 pull_model "$m" $((i * span)) "$span" || fail "Download del modello $m non riuscito"
            model_present "$m" || fail "Modello $m non disponibile dopo il download"
        fi
        i=$((i + 1))
        progress $((i * span)) "Rete neurale pronta: $m"
    done
    progress 100 "Reti neurali installate"
}

step_main "$@"
