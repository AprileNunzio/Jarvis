import os
import socket
import time

import psutil

_last_net = {"t": time.time(), "rx": 0, "tx": 0}


def _primary_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _temperature() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        if temps.get(key):
            return round(max(t.current for t in temps[key]), 1)
    return None


def collect() -> dict:
    net = psutil.net_io_counters()
    now = time.time()
    dt = max(now - _last_net["t"], 0.001)
    rx_rate = (net.bytes_recv - _last_net["rx"]) / dt if _last_net["rx"] else 0
    tx_rate = (net.bytes_sent - _last_net["tx"]) / dt if _last_net["tx"] else 0
    _last_net.update(t=now, rx=net.bytes_recv, tx=net.bytes_sent)

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    return {
        "hostname": socket.gethostname(),
        "ip": _primary_ip(),
        "uptime": int(now - psutil.boot_time()),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(),
        "load": [round(x, 2) for x in load],
        "mem_total": mem.total,
        "mem_used": mem.total - mem.available,
        "mem_percent": mem.percent,
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_percent": disk.percent,
        "net_rx_rate": int(max(rx_rate, 0)),
        "net_tx_rate": int(max(tx_rate, 0)),
        "temperature": _temperature(),
        "time": now,
    }
