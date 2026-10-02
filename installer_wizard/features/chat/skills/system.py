from datetime import datetime

from features.chat.skills.weather import DAYS_IT, MONTHS_IT
from state import store


def system_skill() -> tuple[str, dict]:
    comps = store.components
    sysinfo = store.system or {}
    down = [c["label"] for c in comps.values() if c.get("status") != "ok"]
    items = [{"label": c["label"], "value": c.get("detail", ""), "status": c.get("status", "idle")}
             for c in comps.values()]
    stats = []
    if sysinfo.get("mem_total"):
        stats = [
            {"label": "Processore", "value": f"{sysinfo['cpu_percent']:.0f}%", "percent": sysinfo["cpu_percent"]},
            {"label": "Memoria", "value": f"{sysinfo['mem_percent']:.0f}%", "percent": sysinfo["mem_percent"]},
            {"label": "Disco", "value": f"{sysinfo['disk_percent']:.0f}%", "percent": sysinfo["disk_percent"]},
        ]
        if sysinfo.get("temperature"):
            stats.append({"label": "Temperatura", "value": f"{sysinfo['temperature']} °C",
                          "percent": min(100, sysinfo["temperature"])})
    speech = ("Tutti i sottosistemi sono operativi." if not down
              else f"Attenzione: {', '.join(down)} richied{'e' if len(down) == 1 else 'ono'} attenzione. "
                   "Sto già intervenendo.")
    ui = {"mode": "focus", "title": "Diagnostica di sistema", "subtitle": "Stato in tempo reale",
          "panels": [{"type": "stats", "title": "Risorse", "items": stats},
                     {"type": "list", "title": "Sottosistemi", "items": items}]}
    return speech, ui


def time_skill() -> tuple[str, dict]:
    now = datetime.now()
    speech = (f"Sono le {now.hour}:{now.minute:02d} di {DAYS_IT[now.weekday()].lower()} "
              f"{now.day} {MONTHS_IT[now.month - 1]} {now.year}.")
    return speech, {"mode": "face"}
