import asyncio
import time


async def network_skill() -> tuple[str, dict]:
    from collections import Counter
    from features.network.explorer import explorer
    if time.time() - explorer.last_scan > 120:
        await asyncio.wait_for(explorer.scan(), 200)
    data = explorer.listing()
    online = [d for d in data["devices"] if d.get("online")]
    kinds = Counter(d["type_label"] for d in online)
    stats = [{"label": k, "value": str(n), "percent": min(100, n * 100 / max(1, len(online)))}
             for k, n in kinds.most_common(8)]
    items = [{"label": f"{d['icon']} {d['label']}", "value": d.get("ip", ""), "status": "ok"} for d in online[:40]]
    new = [d for d in online if time.time() - d.get("first_seen", 0) < 24 * 3600 and d.get("type") != "jarvis"]
    speech = explorer.summary_text()
    if new:
        speech += f" {len(new)} {'è nuovo' if len(new) == 1 else 'sono nuovi'} nelle ultime 24 ore."
    return speech, {"mode": "focus", "title": f"Rete {data['subnet']}", "subtitle": "Dispositivi connessi ora",
                    "panels": [{"type": "stats", "title": "Per tipo", "items": stats},
                               {"type": "list", "title": f"Connessi ({len(online)})", "items": items}]}
