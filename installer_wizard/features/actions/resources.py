import time

import psutil

from features.actions.common import human_bytes


async def resources_action(text: str) -> tuple[str, dict]:
    mem, disk = psutil.virtual_memory(), psutil.disk_usage("/")
    cpu = psutil.cpu_percent(interval=0.5)
    load = ", ".join(f"{x:.2f}".replace(".", ",") for x in psutil.getloadavg())
    up = int(time.time() - psutil.boot_time())
    from sysinfo import _temperature

    temp = _temperature()
    speech = (
        f"Sto usando {human_bytes(mem.used)} di RAM su {human_bytes(mem.total)} ({mem.percent:.0f}%), "
        f"con {human_bytes(mem.available)} ancora disponibili. Sul disco principale ho occupato {human_bytes(disk.used)} "
        f"su {human_bytes(disk.total)} ({disk.percent:.0f}%), liberi {human_bytes(disk.free)}. "
        f"Il processore è al {cpu:.0f}%" + (f" e la temperatura è {temp:.0f} gradi." if temp else ".")
    )
    stats = [
        {"label": "Memoria", "value": f"{human_bytes(mem.used)} / {human_bytes(mem.total)}", "percent": mem.percent},
        {"label": "Disco /", "value": f"{human_bytes(disk.used)} / {human_bytes(disk.total)}", "percent": disk.percent},
        {"label": f"CPU ({psutil.cpu_count()} core)", "value": f"{cpu:.0f}%", "percent": cpu},
    ]
    if temp:
        stats.append({"label": "Temperatura", "value": f"{temp:.0f} °C", "percent": min(100, temp)})
    kv = {
        "Carico medio": load,
        "Acceso da": f"{up // 86400} g {up % 86400 // 3600} h {up % 3600 // 60} min",
        "Swap": f"{human_bytes(psutil.swap_memory().used)} / {human_bytes(psutil.swap_memory().total)}",
    }
    return speech, {
        "mode": "focus",
        "title": "Risorse",
        "subtitle": "Misurate adesso",
        "panels": [
            {"type": "stats", "title": "Utilizzo", "items": stats},
            {"type": "kv", "title": "Dettagli", "data": kv},
        ],
    }
