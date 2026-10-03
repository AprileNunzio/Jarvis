import io
import re
import tarfile
from typing import Dict, Mapping

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HEADER = 8
_SECTOR = 512


class ArchiveError(ValueError):
    pass


def pack(files: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, content in sorted(files.items()):
            if not _NAME.match(name):
                raise ArchiveError(f"invalid file name: {name}")
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o444
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def frame(payload: bytes) -> bytes:
    body = len(payload).to_bytes(_HEADER, "big") + payload
    return body + b"\0" * (-len(body) % _SECTOR)


def unframe(image: bytes, max_bytes: int) -> bytes:
    if len(image) < _HEADER:
        raise ArchiveError("image too small")
    length = int.from_bytes(image[:_HEADER], "big")
    if length > max_bytes or length > len(image) - _HEADER:
        raise ArchiveError("invalid payload length")
    return image[_HEADER : _HEADER + length]


def unpack(payload: bytes, max_files: int, max_bytes: int) -> Dict[str, bytes]:
    files: Dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
            for member in archive.getmembers():
                if not member.isreg() or not _NAME.match(member.name) or member.name in files:
                    continue
                if len(files) >= max_files or total + member.size > max_bytes:
                    break
                content = archive.extractfile(member).read()
                total += len(content)
                files[member.name] = content
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ArchiveError(f"unreadable archive: {exc}") from exc
    return files
