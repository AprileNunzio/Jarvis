import posixpath
from typing import Dict, Iterable, Optional, Set, Tuple

from server.features.deep_memory.domain.script_extractor import is_script, resolved_dependencies
from server.features.deep_memory.domain.structure import FileParse, StructureGraph


def _module_file(module: str, level: int, importer: str, files: Set[str]) -> Optional[str]:
    if level:
        base = posixpath.dirname(importer)
        for _ in range(level - 1):
            base = posixpath.dirname(base)
        parts = [base] if base else []
    else:
        parts = []
    if module:
        parts.append(module.replace(".", "/"))
    stem = posixpath.join(*parts) if parts else ""
    for candidate in (f"{stem}.py", posixpath.join(stem, "__init__.py")):
        if candidate in files:
            return candidate
    return None


def _import_targets(parse: FileParse, files: Set[str], defined: Set[str]) -> Dict[str, Tuple[Optional[str], str]]:
    targets: Dict[str, Tuple[Optional[str], str]] = {}
    for imp in parse.imports:
        file = _module_file(imp.module, imp.level, parse.path, files)
        if imp.member:
            submodule = _module_file(f"{imp.module}.{imp.member}" if imp.module else imp.member, imp.level, parse.path, files)
            if file and f"{file}::{imp.member}" in defined:
                targets[imp.alias] = (file, imp.member)
            elif submodule:
                targets[imp.alias] = (submodule, "")
            elif file:
                targets[imp.alias] = (file, "")
        elif file:
            targets[imp.alias] = (file, "")
    return targets


def _edges_for_python(parse: FileParse, files: Set[str], defined: Set[str]) -> Set[Tuple[str, str]]:
    edges: Set[Tuple[str, str]] = set()
    imports = _import_targets(parse, files, defined)
    for target_file, member in imports.values():
        edges.add((parse.path, f"{target_file}::{member}" if member else target_file))
    for symbol_id, refs in parse.refs.items():
        for name in refs.names:
            local = f"{parse.path}::{name}"
            if local in defined and local != symbol_id:
                edges.add((symbol_id, local))
            elif name in imports:
                target_file, member = imports[name]
                edges.add((symbol_id, f"{target_file}::{member}" if member else target_file))
        for base, attribute in refs.attributes:
            if base in imports and imports[base][1] == "":
                target_file = imports[base][0]
                attr_id = f"{target_file}::{attribute}"
                edges.add((symbol_id, attr_id if attr_id in defined else target_file))
    return edges


def build_graph(parses: Iterable[FileParse]) -> StructureGraph:
    ordered = list(parses)
    files = {p.path for p in ordered}
    symbols = {s.symbol_id: s for p in ordered for s in p.symbols}
    defined = set(symbols)
    edges: Set[Tuple[str, str]] = set()
    for parse in ordered:
        if is_script(parse.path):
            edges.update((parse.path, dep) for dep in resolved_dependencies(parse, files))
        else:
            edges.update(_edges_for_python(parse, files, defined))
    return StructureGraph(symbols, frozenset(e for e in edges if e[0] != e[1]))

