import asyncio
import shutil
import tempfile
from pathlib import Path

CANDIDATES = ("soffice", "libreoffice", r"C:\Program Files\LibreOffice\program\soffice.exe",
              "/usr/lib/libreoffice/program/soffice", "/opt/libreoffice/program/soffice")
FILTERS = {"odt": "odt", "ods": "ods", "odp": "odp", "pdf": "pdf"}
TIMEOUT = 180
_slots = asyncio.Semaphore(2)


def office() -> str | None:
    for name in CANDIDATES:
        found = shutil.which(name) or (name if Path(name).is_file() else None)
        if found:
            return found
    return None


async def convert(source: Path, target_ext: str, out_dir: Path | None = None, export: str | None = None) -> Path:
    binary = office()
    if not binary:
        raise RuntimeError("LibreOffice non è installato: lo installa il passo «Ufficio» dell'installazione")
    out_dir = out_dir or source.parent
    async with _slots:
        with tempfile.TemporaryDirectory(prefix="jarvis-office-") as profile, tempfile.TemporaryDirectory(prefix="jarvis-out-") as tmp:
            proc = await asyncio.create_subprocess_exec(
                binary, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--norestore", "--nologo",
                "--convert-to", export or FILTERS[target_ext], "--outdir", tmp, str(source),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("conversione troppo lenta")
            produced = Path(tmp) / f"{source.stem}.{target_ext}"
            if not produced.exists():
                raise RuntimeError(f"conversione non riuscita: {out.decode(errors='ignore')[-200:]}")
            target = out_dir / produced.name
            shutil.move(str(produced), target)
            return target
