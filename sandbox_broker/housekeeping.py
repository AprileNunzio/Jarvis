import os
import shutil
import subprocess
import time

from sandbox_broker.config import BrokerConfig

_STALE_SECONDS = 3600


def remove_stray_containers(config: BrokerConfig) -> None:
    try:
        listing = subprocess.run(
            [config.docker_bin, "ps", "-aq", "--filter", f"name={config.container_prefix}"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        ids = listing.stdout.split()
        if ids:
            subprocess.run([config.docker_bin, "rm", "-f", *ids], capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return


def remove_stale_workspaces(config: BrokerConfig, now: float = None) -> None:
    now = time.time() if now is None else now
    try:
        entries = list(os.scandir(config.work_dir))
    except OSError:
        return
    for entry in entries:
        if entry.is_dir(follow_symlinks=False) and now - entry.stat(follow_symlinks=False).st_mtime > _STALE_SECONDS:
            shutil.rmtree(entry.path, ignore_errors=True)
