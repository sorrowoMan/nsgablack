"""Resolve explicit inherited declarations from source without importing Cases.

Only static class definitions and source-resolvable imports are followed. Dynamic factories
and ambiguous aliases stay unresolved and retain the ordinary Doctor finding.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


class SourceContractResolver:
    def __init__(self):
        self._trees: dict[Path, ast.Module | None] = {}
        self._packages = {"nsgablack": Path(__file__).resolve().parents[2]}
        for name in ("blackbase", "mlblack"):
            spec = importlib.util.find_spec(name)
            if spec is not None and spec.submodule_search_locations:
                self._packages[name] = Path(next(iter(spec.submodule_search_locations)))

    def _tree(self, path: Path):
        if path not in self._trees:
            try:
                self._trees[path] = ast.parse(path.read_text(encoding="utf-8-sig"))
            except (OSError, SyntaxError, UnicodeError):
                self._trees[path] = None
        return self._trees[path]

    def _module_path(self, source: Path, module: str | None, level: int) -> Path | None:
        parts = (module or "").split(".") if module else []
        if level:
            base = source.parent
            for _ in range(level - 1):
                base = base.parent
        else:
            if not parts or parts[0] not in self._packages:
                return None
            base = self._packages[parts.pop(0)]
        target = base.joinpath(*parts)
        # Python resolves a package before a same-name legacy module shim.
        for candidate in (target / "__init__.py", target.with_suffix(".py")):
            if candidate.is_file():
                return candidate
        return None

    def _class(self, path: Path, name: str, active: set):
        token = (path, name)
        if token in active:
            return None
        active = {*active, token}
        tree = self._tree(path)
        if tree is None:
            return None
        bindings = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                bindings.append(node)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                    bindings.append(node)
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) == name:
                        bindings.append((node, alias))
        if not bindings and not name.startswith("_"):
            exported = []
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not any(alias.name == "*" for alias in node.names):
                    continue
                origin = self._module_path(path, node.module, node.level)
                target = self._tree(origin) if origin is not None else None
                if target is None:
                    continue
                explicit = [item for item in target.body if isinstance(item, ast.Assign)
                            and any(isinstance(key, ast.Name) and key.id == "__all__" for key in item.targets)]
                if explicit:
                    try:
                        names = ast.literal_eval(explicit[-1].value)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(names, (list, tuple, set)) or not all(isinstance(item, str) for item in names):
                        continue
                    if name not in names:
                        continue
                found = self._class(origin, name, active)
                if found is not None and found not in exported:
                    exported.append(found)
            return exported[0] if len(exported) == 1 else None
        if len(bindings) != 1:
            return None
        binding = bindings[0]
        if isinstance(binding, ast.ClassDef):
            return path, binding
        if isinstance(binding, tuple):
            node, alias = binding
            origin = self._module_path(path, node.module, node.level)
            if origin is not None:
                return self._class(origin, alias.name, active)
        return None

    def _linearization(self, path: Path, node: ast.ClassDef, active=None):
        """C3 order for statically resolvable bases; invalid cycles fail closed."""
        active = set(active or ())
        token = (path, node.name)
        if token in active:
            raise ValueError("cyclic source inheritance")
        active.add(token)
        bases = []
        for base in node.bases:
            if not isinstance(base, ast.Name):
                continue
            resolved = self._class(path, base.id, set())
            if resolved:
                bases.append(resolved)
        sequences = [self._linearization(*base, active) for base in bases] + [list(bases)]
        result = [(path, node)]
        while any(sequences):
            sequences = [sequence for sequence in sequences if sequence]
            head = next((sequence[0] for sequence in sequences
                         if not any(sequence[0] in other[1:] for other in sequences)), None)
            if head is None:
                raise ValueError("inconsistent source inheritance")
            result.append(head)
            for sequence in sequences:
                if sequence[0] == head:
                    sequence.pop(0)
        return result

    def declarations(self, path: Path, node: ast.ClassDef, keys: set[str], active=None):
        try:
            lineage = self._linearization(path, node, active)
        except ValueError:
            lineage = [(path, node)]
        merged = {}
        for _, owner in reversed(lineage):
            for item in owner.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "get_context_contract":
                    merged[item.name] = item
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    targets = item.targets if isinstance(item, ast.Assign) else (item.target,)
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id in keys:
                            merged[target.id] = item
        return merged
