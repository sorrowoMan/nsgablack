"""Read-only, conservative API binding checks for generated teaching code.

No inspected component module or generated code is imported or executed. ``ok`` means
that no definite binding error was found; it is not a correctness certificate.
Calls whose receiver/signature cannot be closed from the supplied source trees
are reported as ``unknown_calls`` and never silently counted as verified.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import threading
from typing import Any, Mapping


_FRAMEWORKS = frozenset({"blackbase", "nsgablack", "mlblack"})
_MAX_SOURCE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class _Ref:
    kind: str
    module: str = ""
    name: str = ""


_UNKNOWN = _Ref("unknown")


@dataclass
class _Module:
    name: str
    path: Path
    label: str
    package: bool
    tree: ast.Module


@dataclass(frozen=True)
class _Signature:
    positional: tuple[str, ...]
    positional_only: frozenset[str]
    required: frozenset[str]
    keyword_only: frozenset[str] = frozenset()
    varargs: bool = False
    varkw: bool = False


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return left + "." + node.attr if left else node.attr
    return ""


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.List, ast.Tuple)):
        return set().union(*(_target_names(item) for item in node.elts)) if node.elts else set()
    return set()


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef, *, bound: bool) -> _Signature:
    arguments = node.args
    positional = [item.arg for item in (*arguments.posonlyargs, *arguments.args)]
    required = set(positional[:len(positional) - len(arguments.defaults)])
    positional_only = {item.arg for item in arguments.posonlyargs}
    if bound and positional:
        first = positional.pop(0)
        required.discard(first)
        positional_only.discard(first)
    keyword_only = {item.arg for item in arguments.kwonlyargs}
    required.update(item.arg for item, value in zip(arguments.kwonlyargs, arguments.kw_defaults) if value is None)
    return _Signature(tuple(positional), frozenset(positional_only), frozenset(required),
                      frozenset(keyword_only), arguments.vararg is not None, arguments.kwarg is not None)


class _Sources:
    def __init__(self, roots: Mapping[str, str | Path]):
        self.roots = {name: Path(value).resolve() for name, value in roots.items() if name in _FRAMEWORKS}
        self.modules: dict[str, _Module | None] = {}
        self.symbols: dict[tuple[str, str], _Ref] = {}

    def module(self, name: str) -> _Module | None:
        if name in self.modules:
            return self.modules[name]
        self.modules[name] = None
        parts = name.split(".")
        if not parts or parts[0] not in self.roots or any(not part.isidentifier() for part in parts):
            return None
        framework, suffix = parts[0], parts[1:]
        root = self.roots[framework]
        bases = [root / "src" / framework, root, root / framework]
        for base in bases:
            stem = base.joinpath(*suffix)
            candidates = [(stem.with_suffix(".py"), False), (stem / "__init__.py", True)] if suffix else [(base / "__init__.py", True)]
            for path, package in candidates:
                try:
                    resolved = path.resolve()
                    if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.stat().st_size > _MAX_SOURCE_BYTES:
                        continue
                    tree = ast.parse(resolved.read_text(encoding="utf-8-sig"), filename=str(resolved))
                except (OSError, UnicodeError, SyntaxError, ValueError):
                    continue
                result = _Module(name, resolved, framework + "/" + resolved.relative_to(root).as_posix(), package, tree)
                self.modules[name] = result
                return result
        return None

    @staticmethod
    def import_module(current: _Module, node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        package = current.name.split(".") if current.package else current.name.split(".")[:-1]
        if node.level > len(package):
            return ""
        prefix = package[:len(package) - node.level + 1]
        return ".".join((*prefix, *((node.module or "").split(".") if node.module else ())))

    def symbol(self, module_name: str, name: str, seen: frozenset[tuple[str, str]] = frozenset()) -> _Ref:
        key = (module_name, name)
        if key in self.symbols:
            return self.symbols[key]
        if key in seen or len(seen) > 40:
            return _UNKNOWN
        source = self.module(module_name)
        if source is None:
            return _UNKNOWN
        seen = seen | {key}
        stars = []
        for node in reversed(source.tree.body):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                result = _Ref("class" if isinstance(node, ast.ClassDef) else "function", module_name, name)
                self.symbols[key] = result
                return result
            if isinstance(node, ast.ImportFrom):
                target = self.import_module(source, node)
                for alias in node.names:
                    if alias.name == "*":
                        stars.append(target)
                    elif (alias.asname or alias.name) == name:
                        result = self.symbol(target, alias.name, seen)
                        if result == _UNKNOWN and self.module(target + "." + alias.name) is not None:
                            result = _Ref("module", target + "." + alias.name)
                        self.symbols[key] = result
                        return result
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.asname or alias.name.split(".")[0]) == name:
                        return _Ref("module", alias.name if alias.asname else alias.name.split(".")[0])
            if isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id == name for item in node.targets):
                return self.expression(source, node.value, seen)
        for target in stars:
            result = self.symbol(target, name, seen)
            if result != _UNKNOWN:
                self.symbols[key] = result
                return result
        if self.module(module_name + "." + name) is not None:
            return _Ref("module", module_name + "." + name)
        return _UNKNOWN

    def expression(self, source: _Module, node: ast.AST, seen=frozenset()) -> _Ref:
        if isinstance(node, ast.Name):
            return self.symbol(source.name, node.id, seen)
        if isinstance(node, ast.Attribute):
            parent = self.expression(source, node.value, seen)
            if parent.kind == "module":
                return self.symbol(parent.module, node.attr, seen)
        return _UNKNOWN

    def definition(self, ref: _Ref) -> tuple[_Module, ast.AST] | None:
        source = self.module(ref.module)
        if source is None:
            return None
        node = next((item for item in source.tree.body
                     if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == ref.name), None)
        return None if node is None else (source, node)

    def class_chain(self, ref: _Ref, seen=frozenset()) -> tuple[list[tuple[_Module, ast.ClassDef]], bool]:
        key = (ref.module, ref.name)
        if key in seen or len(seen) > 40:
            return [], False
        definition = self.definition(ref)
        if definition is None or not isinstance(definition[1], ast.ClassDef):
            return [], False
        source, node = definition
        chain, complete = [(source, node)], True
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "object":
                continue
            parent = self.expression(source, base)
            if parent.kind != "class":
                complete = False
                continue
            inherited, known = self.class_chain(parent, seen | {key})
            chain.extend(inherited)
            complete = complete and known
        return chain, complete

    def method(self, ref: _Ref, name: str) -> tuple[_Module, ast.FunctionDef | ast.AsyncFunctionDef, bool] | None:
        chain, _ = self.class_chain(_Ref("class", ref.module, ref.name))
        for source, node in chain:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                    decorators = {_dotted(d.func if isinstance(d, ast.Call) else d).split(".")[-1] for d in item.decorator_list}
                    if "property" in decorators or decorators - {"classmethod", "staticmethod", "abstractmethod"}:
                        return None
                    bound = "classmethod" in decorators or (ref.kind == "instance" and "staticmethod" not in decorators)
                    return source, item, bound
        return None

    def constructor(self, ref: _Ref) -> tuple[_Signature, _Module, int] | None:
        chain, complete = self.class_chain(ref)
        if not chain:
            return None
        source, node = chain[0]
        if any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__new__" for _, parent in chain for item in parent.body):
            return None
        own_init = next((item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__"), None)
        decorators = [item for item in node.decorator_list
                      if _dotted(item.func if isinstance(item, ast.Call) else item).split(".")[-1] == "dataclass"]
        generated = bool(decorators) and not any(isinstance(item, ast.Call) and any(
            kw.arg == "init" and isinstance(kw.value, ast.Constant) and kw.value.value is False
            for kw in item.keywords) for item in decorators)
        if own_init is not None:
            if own_init.decorator_list:
                return None
            return _function_signature(own_init, bound=True), source, own_init.lineno
        if generated:
            if not complete:
                return None
            fields: dict[str, tuple[bool, bool]] = {}
            for _, parent in reversed(chain):
                if not any(_dotted(item.func if isinstance(item, ast.Call) else item).split(".")[-1] == "dataclass"
                           for item in parent.decorator_list):
                    continue
                dataclass_kwonly = any(isinstance(item, ast.Call) and any(
                    kw.arg == "kw_only" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in item.keywords) for item in parent.decorator_list)
                kwonly = dataclass_kwonly
                for item in parent.body:
                    if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                        continue
                    annotation = _dotted(item.annotation.value if isinstance(item.annotation, ast.Subscript) else item.annotation)
                    if annotation.split(".")[-1] == "ClassVar":
                        continue
                    if annotation.split(".")[-1] == "KW_ONLY":
                        kwonly = True
                        continue
                    required, field_kwonly, include = item.value is None, kwonly, True
                    if isinstance(item.value, ast.Call) and _dotted(item.value.func).split(".")[-1] == "field":
                        arguments = {kw.arg: kw.value for kw in item.value.keywords if kw.arg}
                        include = not (isinstance(arguments.get("init"), ast.Constant) and arguments["init"].value is False)
                        required = "default" not in arguments and "default_factory" not in arguments
                        if isinstance(arguments.get("kw_only"), ast.Constant):
                            field_kwonly = bool(arguments["kw_only"].value)
                    if include:
                        fields[item.target.id] = (required, field_kwonly)
                    else:
                        fields.pop(item.target.id, None)
            return (_Signature(tuple(name for name, (_, kw) in fields.items() if not kw), frozenset(),
                               frozenset(name for name, (required, _) in fields.items() if required),
                               frozenset(name for name, (_, kw) in fields.items() if kw)), source, node.lineno)
        method = self.method(_Ref("instance", ref.module, ref.name), "__init__")
        if method is not None:
            owner, init, _ = method
            return _function_signature(init, bound=True), owner, init.lineno
        if complete:
            return _Signature((), frozenset(), frozenset()), source, node.lineno
        return None

    def missing_method(self, ref: _Ref, name: str) -> bool:
        if name.startswith("__"):
            return False
        chain, complete = self.class_chain(_Ref("class", ref.module, ref.name))
        if not complete:
            return False
        for _, node in chain:
            for item in ast.walk(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in {name, "__getattr__", "__getattribute__"}:
                    return False
                if isinstance(item, ast.Attribute) and isinstance(item.ctx, ast.Store) and item.attr == name:
                    return False
                if isinstance(item, ast.Call) and _dotted(item.func).split(".")[-1] == "setattr":
                    return False
            for item in node.body:
                targets = item.targets if isinstance(item, ast.Assign) else (item.target,) if isinstance(item, ast.AnnAssign) else ()
                if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                    return False
        return bool(chain)


class _Inspector(ast.NodeVisitor):
    def __init__(self, sources: _Sources, env=None):
        self.sources = sources
        self.env: dict[str, _Ref] = dict(env or {})
        self.issues: list[dict[str, Any]] = []
        self.checked: list[dict[str, Any]] = []
        self.unknown: list[dict[str, Any]] = []
        self.returns: list[_Ref] = []
        self.local_returns: dict[str, _Ref] = {}
        self.call_returns: dict[int, _Ref] = {}

    def infer(self, node: ast.AST) -> _Ref:
        if isinstance(node, ast.Name):
            return self.env.get(node.id, _UNKNOWN)
        if isinstance(node, ast.Attribute):
            base = self.infer(node.value)
            if base.kind == "module":
                return self.sources.symbol(base.module, node.attr)
        if isinstance(node, ast.Call):
            return self.call_returns.get(id(node), _UNKNOWN)
        return _UNKNOWN

    def _return_type(self, source: _Module, function: ast.FunctionDef | ast.AsyncFunctionDef, owner: _Ref | None = None) -> _Ref:
        annotation = function.returns
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return _UNKNOWN
        if isinstance(annotation, ast.Name) and annotation.id in {"Self", "cls"} and owner is not None:
            return _Ref("instance", owner.module, owner.name)
        if annotation is not None:
            result = self.sources.expression(source, annotation)
            if result.kind == "class":
                return _Ref("instance", result.module, result.name)
        direct = [item.value for item in function.body if isinstance(item, ast.Return)]
        if len(direct) == 1 and isinstance(direct[0], ast.Call):
            value = direct[0]
            if isinstance(value.func, ast.Name) and value.func.id == "cls" and owner is not None:
                return _Ref("instance", owner.module, owner.name)
            result = self.sources.expression(source, value.func)
            if result.kind == "class":
                return _Ref("instance", result.module, result.name)
        return _UNKNOWN

    def _issue(self, node, code, target, message, source=None, line=None):
        item = {"code": code, "line": int(getattr(node, "lineno", 1)), "target": target, "message": message}
        if source is not None:
            item.update({"source_path": source.label, "source_line": int(line or 1)})
        self.issues.append(item)

    def _bind(self, node: ast.Call, signature: _Signature, target: str, source: _Module, line: int):
        positional = [item for item in node.args if not isinstance(item, ast.Starred)]
        starargs = any(isinstance(item, ast.Starred) for item in node.args)
        starkw = any(item.arg is None for item in node.keywords)
        named = [item.arg for item in node.keywords if item.arg is not None]
        supplied = set(signature.positional[:len(positional)])
        if not starargs and not signature.varargs and len(positional) > len(signature.positional):
            self._issue(node, "usage-api-positional-overflow", target, "Too many positional arguments for the source signature", source, line)
        allowed = (set(signature.positional) - set(signature.positional_only)) | set(signature.keyword_only)
        for name in named:
            if name not in allowed and not signature.varkw:
                self._issue(node, "usage-api-unknown-keyword", target, "Unsupported keyword: " + name, source, line)
            if name in supplied and not starargs:
                self._issue(node, "usage-api-duplicate-argument", target, "Argument supplied more than once: " + name, source, line)
        supplied.update(named)
        if not starargs and not starkw:
            for name in sorted(signature.required - supplied):
                self._issue(node, "usage-api-missing-required", target, "Missing required argument: " + name, source, line)
        self.checked.append({"line": node.lineno, "target": target, "source_path": source.label, "source_line": line})
        if starargs or starkw or (signature.varkw and any(name not in allowed for name in named)):
            self.unknown.append({"line": node.lineno, "target": target, "reason": "dynamic_argument_binding"})

    def visit_Import(self, node):
        for alias in node.names:
            module = alias.name if alias.asname else alias.name.split(".")[0]
            self.env[alias.asname or alias.name.split(".")[0]] = _Ref("module", module)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self.env[alias.asname or alias.name] = self.sources.symbol(node.module or "", alias.name) if not node.level else _UNKNOWN

    def visit_Assign(self, node):
        self.visit(node.value)
        value = self.infer(node.value)
        for target in node.targets:
            for name in _target_names(target):
                self.env[name] = value if isinstance(target, ast.Name) else _UNKNOWN
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                self.env[target.value.id] = _UNKNOWN

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self.visit(node.value)
        if isinstance(node.target, ast.Name):
            self.env[node.target.id] = self.infer(node.value) if node.value is not None else _UNKNOWN

    def visit_Return(self, node):
        if node.value is not None:
            self.visit(node.value)
            self.returns.append(self.infer(node.value))
        else:
            self.returns.append(_UNKNOWN)

    def visit_FunctionDef(self, node):
        self.env[node.name] = _Ref("local_function", name=node.name)
        child = _Inspector(self.sources, self.env)
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            ref = child.infer(argument.annotation) if argument.annotation is not None else _UNKNOWN
            child.env[argument.arg] = _Ref("instance", ref.module, ref.name) if ref.kind == "class" else _UNKNOWN
        if node.args.vararg:
            child.env[node.args.vararg.arg] = _UNKNOWN
        if node.args.kwarg:
            child.env[node.args.kwarg.arg] = _UNKNOWN
        for item in node.body:
            child.visit(item)
        self.issues.extend(child.issues)
        self.checked.extend(child.checked)
        self.unknown.extend(child.unknown)
        if child.returns and all(ref == child.returns[0] for ref in child.returns):
            self.local_returns[node.name] = child.returns[0]

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.env[node.name] = _UNKNOWN  # user classes are not a closed framework API
        child = _Inspector(self.sources, self.env)
        for item in node.body:
            child.visit(item)
        self.issues.extend(child.issues)
        self.checked.extend(child.checked)
        self.unknown.extend(child.unknown)

    def visit_If(self, node):
        self.visit(node.test)
        original = dict(self.env)
        outcomes = []
        for block in (node.body, node.orelse):
            self.env = dict(original)
            for item in block:
                self.visit(item)
            outcomes.append(self.env)
        self.env = {name: outcomes[0].get(name, _UNKNOWN) if outcomes[0].get(name, _UNKNOWN) == outcomes[1].get(name, _UNKNOWN) else _UNKNOWN
                    for name in set(outcomes[0]) | set(outcomes[1])}

    def visit_For(self, node):
        self.visit(node.iter)
        before = dict(self.env)
        for name in _target_names(node.target):
            self.env[name] = _UNKNOWN
        for item in (*node.body, *node.orelse):
            self.visit(item)
        self.env = {name: value if before.get(name, _UNKNOWN) == value else _UNKNOWN for name, value in self.env.items()}

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.visit(node.test)
        before = dict(self.env)
        for item in (*node.body, *node.orelse):
            self.visit(item)
        self.env = {name: value if before.get(name, _UNKNOWN) == value else _UNKNOWN for name, value in self.env.items()}

    def visit_Try(self, node):
        before = dict(self.env)
        outcomes = []
        for block in (node.body, *(handler.body for handler in node.handlers), node.orelse):
            self.env = dict(before)
            for item in block:
                self.visit(item)
            outcomes.append(dict(self.env))
        self.env = {name: outcomes[0].get(name, _UNKNOWN)
                    if all(outcome.get(name, _UNKNOWN) == outcomes[0].get(name, _UNKNOWN) for outcome in outcomes)
                    else _UNKNOWN for name in set().union(*(outcome.keys() for outcome in outcomes))}
        for item in node.finalbody:
            self.visit(item)

    visit_TryStar = visit_Try

    def _comprehension(self, node):
        before = dict(self.env)
        for generator in node.generators:
            self.visit(generator.iter)
            for name in _target_names(generator.target):
                self.env[name] = _UNKNOWN
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.env = before

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension

    def visit_Call(self, node):
        self.generic_visit(node)
        callee = self.infer(node.func)
        result = _UNKNOWN
        target = _dotted(node.func) or "<dynamic>"
        if callee.kind == "class":
            closed = self.sources.constructor(callee)
            if closed is not None:
                signature, source, line = closed
                self._bind(node, signature, callee.module + "." + callee.name, source, line)
                result = _Ref("instance", callee.module, callee.name)
            else:
                self.unknown.append({"line": node.lineno, "target": target, "reason": "constructor_source_not_closed"})
        elif callee.kind == "function":
            definition = self.sources.definition(callee)
            if definition is not None:
                source, function = definition
                if not function.decorator_list:
                    self._bind(node, _function_signature(function, bound=False), callee.module + "." + callee.name, source, function.lineno)
                    result = self._return_type(source, function)
                else:
                    self.unknown.append({"line": node.lineno, "target": target, "reason": "decorated_callable"})
        elif callee.kind == "local_function":
            result = self.local_returns.get(callee.name, _UNKNOWN)
            self.unknown.append({"line": node.lineno, "target": target, "reason": "local_callable"})
        elif isinstance(node.func, ast.Attribute):
            receiver = self.infer(node.func.value)
            if receiver.kind in {"class", "instance"}:
                method = self.sources.method(receiver, node.func.attr)
                if method is not None:
                    source, function, bound = method
                    self._bind(node, _function_signature(function, bound=bound), receiver.module + "." + receiver.name + "." + node.func.attr, source, function.lineno)
                    result = self._return_type(source, function, receiver)
                elif self.sources.missing_method(receiver, node.func.attr):
                    self._issue(node, "usage-api-method-missing", receiver.module + "." + receiver.name + "." + node.func.attr,
                                "Method does not exist on the closed source class")
                else:
                    self.unknown.append({"line": node.lineno, "target": target, "reason": "method_source_not_closed"})
            else:
                self.unknown.append({"line": node.lineno, "target": target, "reason": "receiver_type_unknown"})
        else:
            self.unknown.append({"line": node.lineno, "target": target, "reason": "callable_type_unknown"})
        self.call_returns[id(node)] = result


class UsageApiValidator:
    """Reuse trusted AST sources across a batch of independent code snippets."""

    def __init__(self, source_roots: Mapping[str, str | Path]):
        self.sources = _Sources(source_roots)
        self._lock = threading.RLock()

    def inspect(self, code: str, *, placement: str = "") -> dict[str, Any]:
        with self._lock:
            return self._inspect(code, placement=placement)

    def _inspect(self, code: str, *, placement: str = "") -> dict[str, Any]:
        inspector = _Inspector(self.sources)
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {"ok": False, "issues": [{"code": "usage-api-code-invalid", "line": exc.lineno or 1,
                    "target": "<code>", "message": "Code does not parse as Python"}],
                    "checked_calls": [], "unknown_calls": [], "complete": False}
        inspector.visit(tree)
        formal_case = bool(re.search(r"build_solver\.py|正式\s*case|standard\s+case|canonical\s+case", placement, re.I))
        if formal_case:
            doctor = self.sources.module("blackbase.project.doctor")
            contract_line = None
            if doctor is not None:
                contract_line = next((item.lineno for item in ast.walk(doctor.tree)
                    if isinstance(item, ast.For) and isinstance(item.iter, ast.Tuple)
                    and [value.value for value in item.iter.elts if isinstance(value, ast.Constant)]
                    == ["resource_context", "component_overrides"]), None)
            for function in tree.body:
                if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and function.name == "build_solver":
                    explicit = {arg.arg for arg in (*function.args.args, *function.args.kwonlyargs)}
                    for name in ("resource_context", "component_overrides"):
                        if name not in explicit:
                            inspector._issue(function, "case-build-missing-" + name.replace("_", "-"),
                                             "build_solver", "Formal Case builder must explicitly accept " + name,
                                             doctor if contract_line is not None else None, contract_line)
        return {"ok": not inspector.issues, "issues": inspector.issues,
                "checked_calls": inspector.checked, "unknown_calls": inspector.unknown,
                "complete": not inspector.unknown}


def inspect_usage_api(code: str, *, source_roots: Mapping[str, str | Path], placement: str = "") -> dict[str, Any]:
    """Report proven API errors and unresolved calls without executing code."""
    return UsageApiValidator(source_roots).inspect(code, placement=placement)
