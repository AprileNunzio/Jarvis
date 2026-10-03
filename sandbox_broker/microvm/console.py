import base64
import binascii
from dataclasses import dataclass
from typing import Dict, Optional

MARK = b"@@JARVIS@@"
_OOM_SIGNS = (b"Out of memory", b"oom-kill", b"Killed process")


@dataclass(frozen=True)
class GuestReport:
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: Optional[int] = None
    timed_out: bool = False
    oom_killed: bool = False

    @property
    def complete(self) -> bool:
        return self.exit_code is not None


def parse(console: bytes, cap: int) -> GuestReport:
    fields: Dict[str, bytes] = {}
    oom = False
    for line in console.splitlines():
        line = line.strip()
        if line.startswith(MARK):
            parts = line.split(b" ", 2)
            if len(parts) == 3:
                try:
                    fields[parts[1].decode("ascii", "ignore")] = base64.b64decode(parts[2], validate=True)[:cap]
                except (binascii.Error, ValueError):
                    continue
        elif any(sign in line for sign in _OOM_SIGNS):
            oom = True
    code: Optional[int] = None
    if "exit" in fields:
        try:
            code = int(fields["exit"].decode("ascii"))
        except ValueError:
            code = None
    return GuestReport(
        stdout=fields.get("stdout", b""),
        stderr=fields.get("stderr", b""),
        exit_code=code,
        timed_out=fields.get("timeout") == b"1",
        oom_killed=oom or (code is not None and code in (137, -9) and fields.get("timeout") != b"1"),
    )


def tail(console_bytes: bytes, process_stderr: bytes, lines: int = 7, limit: int = 560) -> str:
    kept = [ln.strip() for ln in console_bytes.decode("utf-8", "replace").splitlines() if ln.strip() and MARK.decode() not in ln and "[anonymous-instance" not in ln]
    err = " ".join(process_stderr.decode("utf-8", "replace").split())[-160:]
    text = " / ".join(kept[-lines:])
    return f"console: {text[-limit:]}" + (f" | vmm: {err}" if err else "")
