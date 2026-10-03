import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, List


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    duration_ms: int


def _drain(stream, cap: int, sink: List[bytes]) -> None:
    kept = 0
    for chunk in iter(lambda: stream.read(65536), b""):
        room = cap - kept
        if room > 0:
            sink.append(chunk[:room])
            kept += min(len(chunk), room)


def run_capped(argv: List[str], wall_seconds: float, cap_bytes: int, on_timeout: Callable[[], None]) -> ProcessResult:
    started = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out: List[bytes] = []
    err: List[bytes] = []
    readers = [
        threading.Thread(target=_drain, args=(proc.stdout, cap_bytes, out), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, cap_bytes, err), daemon=True),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        proc.wait(timeout=wall_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        on_timeout()
        proc.kill()
        proc.wait()
    for reader in readers:
        reader.join(timeout=5)
    return ProcessResult(
        exit_code=proc.returncode,
        stdout=b"".join(out),
        stderr=b"".join(err),
        timed_out=timed_out,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
