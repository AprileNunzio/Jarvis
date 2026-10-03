import ast
import hashlib
from typing import Dict, List, Set, Tuple

from server.features.deep_memory.domain.structure import MODULE_KIND, FileParse, ImportRef, RawRefs, Symbol


class SourceError(ValueError):
    pass


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _references(node: ast.AST) -> RawRefs:
    names: Set[str] = set()
    attributes: Set[Tuple[str, str]] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            names.add(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            attributes.add((child.value.id, child.attr))
    return RawRefs(frozenset(names), frozenset(attributes))


def _imports(tree: ast.Module) -> Tuple[ImportRef, ...]:
    found: List[ImportRef] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(ImportRef(alias.asname or alias.name.split(".")[0], alias.name))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                found.append(ImportRef(alias.asname or alias.name, node.module or "", alias.name, node.level))
    return tuple(found)


def _target_names(node: ast.AST) -> List[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [t.id for t in targets if isinstance(t, ast.Name)]


def _collect(path: str, node: ast.AST, prefix: str, symbols: List[Symbol], refs: Dict[str, RawRefs]) -> None:
    qualname = f"{prefix}{node.name}"
    kind = "class" if isinstance(node, ast.ClassDef) else "function"
    symbol_id = f"{path}::{qualname}"
    symbols.append(Symbol(symbol_id, kind, node.name, _digest(_dump(node))))
    own = ast.Module(body=[n for n in node.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))] if kind == "class" else node.body, type_ignores=[])
    header = _references(ast.Module(body=[ast.Expr(value=b) for b in getattr(node, "bases", [])] + [ast.Expr(value=d) for d in node.decorator_list], type_ignores=[]))
    body = _references(own)
    refs[symbol_id] = RawRefs(header.names | body.names, header.attributes | body.attributes)
    if kind == "class":
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _collect(path, child, f"{qualname}.", symbols, refs)


def extract_python(path: str, source: str) -> FileParse:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SourceError(f"{path}: {exc.msg} at line {exc.lineno}") from exc
    symbols: List[Symbol] = []
    refs: Dict[str, RawRefs] = {}
    module_statements: List[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _collect(path, node, "", symbols, refs)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in _target_names(node):
                symbol_id = f"{path}::{name}"
                symbols.append(Symbol(symbol_id, "variable", name, _digest(_dump(node))))
                refs[symbol_id] = _references(node.value) if node.value is not None else RawRefs()
        else:
            module_statements.append(node)
    module_dump = "".join(_dump(n) for n in module_statements)
    symbols.insert(0, Symbol(path, MODULE_KIND, path, _digest(module_dump)))
    refs[path] = _references(ast.Module(body=[n for n in module_statements if not isinstance(n, (ast.Import, ast.ImportFrom))], type_ignores=[]))
    return FileParse(path, _digest(source), tuple(symbols), refs, _imports(tree))
