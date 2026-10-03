import hashlib
import posixpath
import re
from typing import FrozenSet, Iterable, Optional, Set

from server.features.deep_memory.domain.structure import MODULE_KIND, FileParse, Symbol

SCRIPT_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
_SPECIFIER = re.compile(
    r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|export\s+[^'"]*?\s+from\s+|require\(\s*|import\(\s*)['"]([^'"]+)['"]"""
)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(?m)(?<![:\"'])//.*$")


def is_script(path: str) -> bool:
    return path.lower().endswith(SCRIPT_EXTENSIONS)


def _normalise(source: str) -> str:
    stripped = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))
    return re.sub(r"\s+", " ", stripped).strip()


def specifiers(source: str) -> FrozenSet[str]:
    return frozenset(m.group(1) for m in _SPECIFIER.finditer(source))


def resolve_specifier(importer: str, specifier: str, known_files: Iterable[str]) -> Optional[str]:
    if not specifier.startswith("."):
        return None
    known = set(known_files)
    base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), specifier))
    candidates = [base] + [base + ext for ext in SCRIPT_EXTENSIONS] + [posixpath.join(base, "index" + ext) for ext in SCRIPT_EXTENSIONS]
    return next((c for c in candidates if c in known), None)


def extract_script(path: str, source: str) -> FileParse:
    digest = hashlib.sha256(_normalise(source).encode("utf-8")).hexdigest()[:20]
    return FileParse(
        path=path,
        fingerprint=digest,
        symbols=(Symbol(path, MODULE_KIND, path, digest),),
        direct_dependencies=specifiers(source),
    )


def resolved_dependencies(parse: FileParse, known_files: Iterable[str]) -> Set[str]:
    known = list(known_files)
    return {t for t in (resolve_specifier(parse.path, s, known) for s in parse.direct_dependencies) if t}
