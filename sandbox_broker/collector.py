import os
import re
import stat
from typing import List, Tuple

from server.features.sandbox.domain.report import Artifact
from server.features.sandbox.domain.spec import MAX_INPUT_FILES, ResourceLimits

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def collect(out_dir: str, limits: ResourceLimits) -> Tuple[Tuple[Artifact, ...], bool]:
    artifacts: List[Artifact] = []
    total = 0
    truncated = False
    for entry in sorted(os.scandir(out_dir), key=lambda e: e.name):
        info = entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or not _NAME.match(entry.name):
            truncated = True
            continue
        if len(artifacts) >= MAX_INPUT_FILES or total + info.st_size > limits.output_bytes:
            truncated = True
            continue
        with open(entry.path, "rb") as handle:
            content = handle.read(limits.output_bytes + 1)
        if len(content) != info.st_size:
            truncated = True
            continue
        total += len(content)
        artifacts.append(Artifact(entry.name, content))
    return tuple(artifacts), truncated
