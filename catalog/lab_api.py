"""Source-backed Python API evidence without importing or constructing components.

The index is derived from the current packaged source on every lookup.  It is
neither a second API registry nor a type checker: unresolved bases, decorators,
and dynamic attributes are disclosed rather than guessed away.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import lru_cache
import hashlib
from importlib.util import find_spec
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


SCHEMA = "nsgablack.lab_api/v1"
_ROOT = Path(__file__).resolve().parent.parent
_DIRECTORIES = ("adapters", "core", "units", "representation", "project", "bias", "plugins")
_EXCLUDED = {"scaffold", "templates", "examples", "tests", "__pycache__"}
_SYMBOL = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){0,24}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_FILE_BYTES = 512000
_MAX_RESULT_BYTES = 32000
_SHARED_PREFIX = "@blackbase/"
_SHARED_FILES = ("types.py",)


def _shared_root():
    # Looking up a top-level package spec locates its installed source without
    # importing it. No arbitrary dependency/module names come from the model.
    spec = find_spec("blackbase")
    if spec is None or not spec.origin:
        raise ValueError("shared_api_source_unavailable")
    return Path(spec.origin).parent


def _linked(path):
    information = path.lstat()
    return path.is_symlink() or bool(getattr(information, "st_file_attributes", 0)
                                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _safe_path(relative):
    if not isinstance(relative, str):
        raise ValueError("api_source_refused")
    if relative.startswith(_SHARED_PREFIX):
        filename = relative[len(_SHARED_PREFIX):]
        if filename not in _SHARED_FILES:
            raise ValueError("api_source_refused")
        root = _shared_root()
        path = root / filename
        if _linked(root) or _linked(path):
            raise ValueError("api_source_refused")
        path.resolve().relative_to(root.resolve())
        return path
    item = PurePosixPath(relative)
    if (not isinstance(relative, str) or item.is_absolute() or ".." in item.parts
            or "\\" in relative or ":" in relative or item.as_posix() != relative
            or len(item.parts) < 2 or item.parts[0] not in _DIRECTORIES
            or set(item.parts).intersection(_EXCLUDED) or item.suffix != ".py"):
        raise ValueError("api_source_refused")
    path = _ROOT.joinpath(*item.parts)
    for node in (path, *path.parents):
        if _linked(node):
            raise ValueError("api_source_refused")
        if node == _ROOT:
            break
    path.resolve().relative_to(_ROOT.resolve())
    return path


def _read(relative):
    path = _safe_path(relative)
    before = path.stat()
    if before.st_size > _MAX_FILE_BYTES:
        raise ValueError("api_source_too_large")
    data = path.read_bytes()
    after = path.stat()
    if (len(data) > _MAX_FILE_BYTES
            or (after.st_size, after.st_mtime_ns, after.st_ino) != (before.st_size, before.st_mtime_ns, before.st_ino)):
        raise ValueError("api_source_changed")
    _safe_path(relative)
    return data.decode("utf-8-sig"), hashlib.sha256(data).hexdigest()


def _validate_symbol(value):
    if not isinstance(value, str) or len(value) > 240 or not _SYMBOL.fullmatch(value):
        raise ValueError("api_symbol_invalid")
    return value


def _expr(node, limit=400):
    return None if node is None else ast.unparse(node)[:limit]


def _source(module, node):
    return {"path": module.path, "sha256": module.sha256,
            "line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno)}


class _Module:
    def __init__(self, name, path, source, sha256):
        self.name, self.path, self.source, self.sha256 = name, path, source, sha256
        self.tree = ast.parse(source)
        self.definitions = {node.name: node for node in self.tree.body
                            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        self.imports = {}
        self.aliases = {}
        self.reference_sources = {}
        self.rebound = set()
        seen = set()
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        for node in self.tree.body:
            bindings = []
            if isinstance(node, ast.ImportFrom):
                parts = package.split(".")
                prefix = parts[:len(parts) - node.level + 1] if node.level else []
                target = ".".join(prefix + ([node.module] if node.module else []))
                for alias in node.names:
                    if alias.name != "*":
                        local = alias.asname or alias.name
                        self.imports[local] = target + "." + alias.name
                        self.reference_sources[local] = _source(self, node)
                        bindings.append(local)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    self.imports[local] = alias.name if alias.asname else alias.name.split(".")[0]
                    self.reference_sources[local] = _source(self, node)
                    bindings.append(local)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                bindings.append(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                bindings = [target.id for target in targets if isinstance(target, ast.Name)]
                expression = _expr(node.value)
                if expression and _SYMBOL.fullmatch(expression):
                    root, *suffix = expression.split(".")
                    target = (self.aliases.get(root) or self.imports.get(root)
                              or (self.name + "." + root if root in seen and root in self.definitions else None))
                    if target and root not in self.rebound:
                        for local in bindings:
                            self.aliases[local] = ".".join((target, *suffix))
                            self.reference_sources[local] = _source(self, node)
            for local in bindings:
                if local in seen:
                    # Resolving overwritten aliases requires value-flow analysis;
                    # do not silently follow a new object through an old alias.
                    self.rebound.add(local)
                seen.add(local)
        self.bound_names = seen


class _Index:
    def __init__(self, modules):
        self.modules = modules
        self.symbols = {module.name + "." + name: (module, node)
                        for module in modules.values() for name, node in module.definitions.items()}

    def resolve_trace(self, symbol, seen=()):
        if symbol in seen or len(seen) > 16:
            return None, []
        module_name, _, local = symbol.rpartition(".")
        module = self.modules.get(module_name)
        if module and local in module.rebound:
            return None, []
        if symbol in self.symbols:
            return self.symbols[symbol], []
        target = None if module is None else module.aliases.get(local, module.imports.get(local))
        if target:
            resolved, trace = self.resolve_trace(target, (*seen, symbol))
            return resolved, [module.reference_sources[local], *trace]
        return None, []

    def resolve(self, symbol, seen=()):
        return self.resolve_trace(symbol, seen)[0]

    def candidates(self, symbol):
        canonical = symbol if symbol.startswith(("nsgablack.", "blackbase.")) else "nsgablack." + symbol
        exact, trace = self.resolve_trace(canonical)
        if exact:
            return [(*exact, trace)]
        if "." in symbol:
            return []
        found = {}
        for module in self.modules.values():
            if symbol not in set(module.definitions) | set(module.imports) | set(module.aliases):
                continue
            pair, trace = self.resolve_trace(module.name + "." + symbol)
            if pair:
                key = (pair[0].path, pair[1].lineno)
                candidate = (*pair, trace)
                if key not in found or len(trace) < len(found[key][2]):
                    found[key] = candidate
        return list(found.values())

    def base(self, module, node):
        if isinstance(node, ast.Subscript):
            node = node.value
        expression = _expr(node)
        if expression == "object":
            return "object", None, []
        pieces = expression.split(".")
        reference = module.aliases.get(pieces[0], module.imports.get(pieces[0]))
        if reference:
            target = ".".join((reference, *pieces[1:]))
        else:
            target = module.name + "." + expression
        resolved, trace = self.resolve_trace(target)
        if reference and pieces[0] in module.reference_sources:
            trace = [module.reference_sources[pieces[0]], *trace]
        return expression, resolved, trace


@lru_cache(maxsize=512)
def _parsed_module(name, path, source, sha256):
    # Only parsing is cached. Every framework lookup still reads and hashes
    # the current source bytes before reaching this process-local bounded cache.
    return _Module(name, path, source, sha256)


def _index():
    modules = {}
    for directory in _DIRECTORIES:
        base = _ROOT / directory
        if not base.is_dir() or _linked(base):
            continue
        for parent, folders, files in os.walk(base, followlinks=False):
            folders[:] = sorted(name for name in folders if name not in _EXCLUDED
                                and not name.startswith(".") and not _linked(Path(parent) / name))
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = Path(parent) / name
                relative = path.relative_to(_ROOT).as_posix()
                try:
                    source, digest = _read(relative)
                    module_name = "nsgablack." + relative[:-3].replace("/", ".")
                    if module_name.endswith(".__init__"):
                        module_name = module_name[:-9]
                    modules[module_name] = _parsed_module(module_name, relative, source, digest)
                except (OSError, ValueError, SyntaxError, UnicodeError):
                    # Incomplete source cannot supply positive evidence.
                    continue
    for filename in _SHARED_FILES:
        path = _SHARED_PREFIX + filename
        try:
            source, digest = _read(path)
            name = "blackbase." + filename[:-3].replace("/", ".")
            modules[name] = _parsed_module(name, path, source, digest)
        except (OSError, ValueError, SyntaxError, UnicodeError, ImportError):
            # An unavailable dependency remains unknown, never a guessed API.
            continue
    return _Index(modules)


def _parameters(node):
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    rows = []
    for i, (argument, default) in enumerate(zip(positional, defaults)):
        rows.append({"name": argument.arg, "kind": "positional_only" if i < len(args.posonlyargs)
                     else "positional_or_keyword", "required": default is None,
                     "annotation": _expr(argument.annotation), "default": _expr(default)})
    if args.vararg:
        rows.append({"name": args.vararg.arg, "kind": "var_positional", "required": False,
                     "annotation": _expr(args.vararg.annotation), "default": None})
    for argument, default in zip(args.kwonlyargs, args.kw_defaults):
        rows.append({"name": argument.arg, "kind": "keyword_only", "required": default is None,
                     "annotation": _expr(argument.annotation), "default": _expr(default)})
    if args.kwarg:
        rows.append({"name": args.kwarg.arg, "kind": "var_keyword", "required": False,
                     "annotation": _expr(args.kwarg.annotation), "default": None})
    return rows


def _method(module, node, owner, *, function=False):
    decorators = [_expr(item) for item in node.decorator_list]
    kind = ("function" if function else "staticmethod" if "staticmethod" in decorators
            else "classmethod" if "classmethod" in decorators else "property" if "property" in decorators
            or any(item.endswith(".setter") for item in decorators) else "method")
    signature = ("async " if isinstance(node, ast.AsyncFunctionDef) else "") + node.name
    signature += "(" + ast.unparse(node.args) + ")"
    if node.returns:
        signature += " -> " + _expr(node.returns)
    return {"name": node.name, "kind": kind, "owner": owner,
            "signature": signature, "parameters": _parameters(node),
            "returns": _expr(node.returns), "bound": kind in {"method", "classmethod", "property"},
            "decorators": decorators, "source": _source(module, node)}


def _class_members(index, module, node, seen=()):
    symbol = module.name + "." + node.name
    if symbol in seen or len(seen) > 12:
        return {}, {}, [symbol], False, []
    methods, fields, unresolved, dynamic, sources = {}, {}, [], False, [_source(module, node)]
    if any(keyword.arg == "metaclass" for keyword in node.keywords):
        unresolved.append("custom_metaclass")
    if any((_expr(decorator).split("(", 1)[0] not in {"dataclass", "dataclasses.dataclass"})
           for decorator in node.decorator_list):
        dynamic = True
    # For a simple inheritance chain, derived declarations take precedence.
    # Multiple inheritance ordering is explicitly unknown rather than a guessed MRO.
    real_bases = [base for base in node.bases if _expr(base) != "object"]
    if len(real_bases) > 1:
        unresolved.append("multiple_inheritance_mro")
    for base in reversed(node.bases):
        expression, resolved, trace = index.base(module, base)
        sources.extend(trace)
        if resolved and isinstance(resolved[1], ast.ClassDef):
            inherited = _class_members(index, *resolved, (*seen, symbol))
            methods.update(inherited[0]); fields.update(inherited[1])
            unresolved.extend(inherited[2]); dynamic |= inherited[3]; sources.extend(inherited[4])
        elif expression != "object":
            unresolved.append(expression)
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name in {"__getattr__", "__getattribute__"}:
                dynamic = True
            # A property setter does not replace the getter signature.
            if item.name not in methods or not any((_expr(d) or "").endswith(".setter") for d in item.decorator_list):
                methods[item.name] = _method(module, item, symbol)
            for nested in ast.walk(item):
                if isinstance(nested, (ast.Assign, ast.AnnAssign)):
                    targets = nested.targets if isinstance(nested, ast.Assign) else [nested.target]
                    for target in targets:
                        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            fields.setdefault(target.attr, {"name": target.attr, "kind": "instance_assignment",
                                "owner": symbol, "annotation": _expr(getattr(nested, "annotation", None)),
                                "default": None, "source": _source(module, nested)})
                if (isinstance(nested, ast.Call) and _expr(nested.func) in {"setattr", "object.__setattr__"}
                        and len(nested.args) >= 2 and isinstance(nested.args[0], ast.Name)
                        and nested.args[0].id == "self"):
                    name = nested.args[1]
                    if isinstance(name, ast.Constant) and isinstance(name.value, str):
                        fields.setdefault(name.value, {"name": name.value, "kind": "instance_assignment",
                            "owner": symbol, "annotation": None, "default": None, "source": _source(module, nested)})
                    else:
                        dynamic = True
        elif isinstance(item, (ast.Assign, ast.AnnAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    fields[target.id] = {"name": target.id, "kind": "declared_field", "owner": symbol,
                        "annotation": _expr(getattr(item, "annotation", None)),
                        "default": _expr(item.value), "source": _source(module, item)}
    return methods, fields, list(dict.fromkeys(unresolved)), dynamic, sources


def _body(module, source):
    lines = module.source.splitlines()
    text = "\n".join(lines[source["line"] - 1:source["end_line"]])
    truncated = len(text) > 8000 or source["end_line"] - source["line"] >= 100
    return "\n".join(text[:8000].splitlines()[:100]), truncated


class _ReturnInference:
    """Small source-only return analysis, never an evaluator or general typer.

    Only a single agreed type across every successful return is reported.
    Dynamic calls, different branch types, loops and unresolved fields remain
    unknown. Evidence includes delegated functions and constructor assignments.
    """

    def __init__(self, index):
        self.index, self.sources, self.remaining = index, {}, 4000

    def record(self, module, node):
        row = _source(module, node)
        self.sources[(row["path"], row["line"])] = row

    def resolve(self, module, expression):
        parts = expression.split(".")
        target = module.aliases.get(parts[0], module.imports.get(parts[0]))
        symbol = ".".join((target, *parts[1:])) if target else module.name + "." + expression
        pair, trace = self.index.resolve_trace(symbol)
        for row in trace:
            self.sources[(row["path"], row["line"])] = row
        if target and parts[0] in module.reference_sources:
            row = module.reference_sources[parts[0]]
            self.sources[(row["path"], row["line"])] = row
        return pair

    def method(self, module, owner, name, seen):
        own = next((n for n in owner.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
        if own is not None:
            return self.function(module, own, owner, seen)
        if len(owner.bases) == 1:
            _, parent, trace = self.index.base(module, owner.bases[0])
            for row in trace:
                self.sources[(row["path"], row["line"])] = row
            if parent and isinstance(parent[1], ast.ClassDef):
                return self.method(*parent, name, seen)
        return None

    @staticmethod
    def agree(values):
        return values[0] if values and values[0] is not None and all(v == values[0] for v in values) else None

    def field(self, module, owner, name, seen):
        key = (module.name, owner.name, "field:" + name)
        if key in seen or len(seen) >= 10:
            return None
        values = []
        for method in owner.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            assignments = [n for n in ast.walk(method) if isinstance(n, (ast.Assign, ast.AnnAssign))
                           and any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                                   and t.value.id == "self" and t.attr == name
                                   for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
            if assignments:
                unsupported = (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)
                if any(isinstance(n, unsupported) and any(n.lineno <= a.lineno <= n.end_lineno for a in assignments)
                       for n in ast.walk(method)):
                    values.append(None)
                    continue
                env = {arg.arg: None for arg in (*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs)}
                for local in ast.walk(method):
                    if isinstance(local, ast.Name) and isinstance(local.ctx, (ast.Store, ast.Del)):
                        env.setdefault(local.id, None)
                self.block(module, method.body, env, owner, (*seen, key), fields=(name, values))
        return self.agree(values)

    def expression(self, module, node, env, owner, seen):
        self.remaining -= 1
        if node is None or self.remaining <= 0:
            return None
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.Constant):
            return ("builtin", "builtins." + type(node.value).__name__)
        if isinstance(node, (ast.Tuple, ast.List, ast.Dict, ast.Set)):
            return ("builtin", "builtins." + {ast.Tuple: "tuple", ast.List: "list", ast.Dict: "dict", ast.Set: "set"}[type(node)])
        if isinstance(node, ast.IfExp):
            return self.agree([self.expression(module, child, env, owner, seen) for child in (node.body, node.orelse)])
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self" and owner:
            return self.field(module, owner, node.attr, seen)
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name) and node.func.id in {"tuple", "list", "dict", "set", "frozenset", "int", "float", "str", "bool"}
                    and node.func.id not in env and node.func.id not in module.bound_names):
                return ("builtin", "builtins." + node.func.id)
            if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self" and owner):
                return self.method(module, owner, node.func.attr, seen)
            text = _expr(node.func)
            if text and _SYMBOL.fullmatch(text) and text.split(".")[0] not in env:
                found = self.resolve(module, text)
                if found:
                    self.record(*found)
                    if isinstance(found[1], ast.ClassDef):
                        methods, _, unresolved, dynamic, sources = _class_members(self.index, *found)
                        for row in sources:
                            self.sources[(row["path"], row["line"])] = row
                        if unresolved or dynamic or "__new__" in methods or found[1].decorator_list or found[1].keywords:
                            return None
                        return ("instance", found[0].name + "." + found[1].name)
                    return self.function(*found, None, seen)
        return None

    def block(self, module, nodes, env, owner, seen, fields=None):
        returns = []
        for node in nodes:
            self.remaining -= 1
            if self.remaining <= 0:
                return [None], env, True
            if isinstance(node, ast.Return):
                return [*returns, self.expression(module, node.value, env, owner, seen)], env, False
            if isinstance(node, ast.Raise):
                return returns, env, False
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = self.expression(module, node.value, env, owner, seen)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = value
                    elif (fields and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                          and target.value.id == "self" and target.attr == fields[0]):
                        self.record(module, node)
                        fields[1].append(value)
            elif isinstance(node, ast.If):
                paths = [self.block(module, body, dict(env), owner, seen, fields)
                         for body in (node.body, node.orelse)]
                for ret, _, _ in paths:
                    returns.extend(ret)
                live = [state for _, state, fall in paths if fall]
                if not live:
                    return returns, env, False
                env = {key: self.agree([state.get(key) for state in live])
                       for key in set().union(*(state.keys() for state in live))}
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)):
                # This deliberately excludes general data/control-flow inference.
                return [None], env, True
        return returns, env, True

    def function(self, module, node, owner=None, seen=()):
        key = (module.name, owner.name if owner else "", node.name)
        if key in seen or len(seen) >= 10:
            return None
        self.record(module, node)
        if isinstance(node, ast.AsyncFunctionDef) or any(_expr(d) not in {"property", "staticmethod"} for d in node.decorator_list):
            return None
        env = {arg.arg: None for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
        for local in ast.walk(node):
            if isinstance(local, ast.Name) and isinstance(local.ctx, (ast.Store, ast.Del)):
                env.setdefault(local.id, None)
        values, _, fall = self.block(module, node.body, env, owner, (*seen, key))
        if fall:
            values.append(("builtin", "builtins.NoneType"))
        return self.agree(values)

    def describe(self, module, node, owner=None):
        value = self.function(module, node, owner)
        result = {"kind": "unknown", "basis": "bounded_source_return_analysis"}
        if value:
            result.update(kind=value[0], symbol=value[1])
        result["sources"] = list(self.sources.values())
        return result


def _factory_value_contract(index, module, assignment, owner):
    """Expose a factory's explicit type declaration without running its body.

    This is a source annotation, not proof of the initialized runtime value.
    Unannotated, decorated, async or dynamic factories remain unknown.
    """
    proof = _ReturnInference(index)
    proof.record(module, assignment)
    result = {"kind": "unknown", "basis": "source_declaration", "runtime_validated": False}
    value = assignment.value
    expression = _expr(value.func) if isinstance(value, ast.Call) else None
    # A class-local alias or method can shadow a module factory. Do not assign
    # its module declaration to a different callable in the class namespace.
    local_names = {node.name for node in owner.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in owner.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        local_names.update(target.id for target in targets if isinstance(target, ast.Name))
    if expression and expression.split(".")[0] in local_names:
        expression = None
    if expression and _SYMBOL.fullmatch(expression):
        factory = proof.resolve(module, expression)
        if factory:
            factory_module, function = factory
            proof.record(factory_module, function)
            if (isinstance(function, ast.FunctionDef) and not function.decorator_list
                    and function.returns is not None):
                annotation = function.returns
                if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                    try:
                        annotation = ast.parse(annotation.value, mode="eval").body
                    except (SyntaxError, ValueError):
                        annotation = None
                name = _expr(annotation)
                declared = proof.resolve(factory_module, name) if name and _SYMBOL.fullmatch(name) else None
                if declared and isinstance(declared[1], ast.ClassDef):
                    proof.record(*declared)
                    result.update(kind="instance", symbol=declared[0].name + "." + declared[1].name,
                        basis="declared_factory_return_annotation", annotation=_expr(function.returns),
                        factory=factory_module.name + "." + function.name,
                        factory_signature=_method(factory_module, function,
                                                  factory_module.name + "." + function.name, function=True)["signature"])
    result["sources"] = list(proof.sources.values())
    return result


def _describe(index, module, node, query, member, scope, resolution_sources=()):
    symbol = module.name + "." + node.name
    result = {"schema": SCHEMA, "status": "found", "query": query, "requested_name": query, "symbol": symbol,
              "source_scope": scope, "source": _source(module, node),
              "kind": "class" if isinstance(node, ast.ClassDef) else "function",
              "limitations": ["Static declarations and observed self assignments, not runtime instances or execution proof."]}
    if isinstance(node, ast.ClassDef):
        methods, fields, unresolved, dynamic, sources = _class_members(index, module, node)
        own_init = any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__"
                       for item in node.body)
        generated_init = any(_expr(item).split("(", 1)[0] in {"dataclass", "dataclasses.dataclass"}
                             and not (isinstance(item, ast.Call) and any(keyword.arg == "init"
                                 and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                                 for keyword in item.keywords)) for item in node.decorator_list)
        if generated_init and not own_init:
            # A generated subclass initializer replaces an inherited initializer.
            # Reporting the latter's signature would validate the wrong call.
            methods.pop("__init__", None)
        result.update(bases=[_expr(base) for base in node.bases], unresolved_bases=unresolved,
                      dynamic_attributes=dynamic, members_complete=not unresolved and not dynamic,
                      member_names=sorted(set(methods) | set(fields)))
        result["constructor_status"] = ("explicit" if own_init else "generated_unresolved" if generated_init
                                        else "inherited_explicit" if "__init__" in methods else "default_unresolved")
        visible_methods = [row for name, row in methods.items() if not name.startswith("_") or name == "__init__"]
        result["methods"] = sorted(visible_methods, key=lambda row: row["name"])[:35]
        result["fields"] = sorted((row for name, row in fields.items() if not name.startswith("_")), key=lambda row: row["name"])[:80]
        result["details_truncated"] = len(visible_methods) > 35 or len(result["fields"]) < len([n for n in fields if not n.startswith("_")])
        if member is not None:
            row = methods.get(member, fields.get(member))
            result["member"] = row
            result["member_status"] = "found" if row else "not_declared" if result["members_complete"] else "unknown"
            result["declared_member_status"] = "found" if row else "unknown" if unresolved else "not_declared"
            if row:
                defining = next((m for m in index.modules.values() if m.path == row["source"]["path"]), None)
                if defining:
                    result["member"] = dict(row, **dict(zip(("excerpt", "truncated"), _body(defining, row["source"]))))
                    method_owner = defining.definitions.get(row["owner"].rsplit(".", 1)[-1])
                    method_node = next((n for n in method_owner.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                        and n.name == row["name"]), None) if isinstance(method_owner, ast.ClassDef) else None
                    if method_node is not None:
                        inferred = _ReturnInference(index).describe(defining, method_node, method_owner)
                        result["member"]["return_contract"] = inferred
                        sources.extend(inferred["sources"])
                    elif row["kind"] == "declared_field" and isinstance(method_owner, ast.ClassDef):
                        assignment = next((n for n in method_owner.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                            and any(isinstance(t, ast.Name) and t.id == member
                                    for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))), None)
                        if assignment is not None:
                            contract = _factory_value_contract(index, defining, assignment, method_owner)
                            result["member"]["value_contract"] = contract
                            sources.extend(contract["sources"])
            # A member query focuses on the requested object, while names stay complete.
            result["methods"] = [row] if row and row["kind"] not in {"declared_field", "instance_assignment"} else []
            result["fields"] = [row] if row and row["kind"] in {"declared_field", "instance_assignment"} else []
    else:
        method = _method(module, node, symbol, function=True)
        result.update(methods=[method], fields=[], sources=[result["source"]], member_names=[],
                      members_complete=False, unresolved_bases=[], dynamic_attributes=False)
        result["member"] = dict(method, **dict(zip(("excerpt", "truncated"), _body(module, result["source"]))))
        result["member"]["return_contract"] = _ReturnInference(index).describe(module, node)
        result["member_status"] = "found" if member is None else "unknown"
        sources = [result["source"]]
        sources.extend(result["member"]["return_contract"]["sources"])
    result["resolution_sources"] = list(resolution_sources)
    result["sources"] = list({row["path"]: row for row in [*sources, *resolution_sources]}.values())
    while len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > _MAX_RESULT_BYTES:
        if len(result["methods"]) > 1:
            result["methods"].pop(); result["details_truncated"] = True
        elif len(result["fields"]) > 1:
            result["fields"].pop(); result["details_truncated"] = True
        else:
            raise ValueError("api_result_too_large")
    return result


def inspect_framework_api(symbol: str, *, member: str | None = None) -> dict:
    """Resolve a current public source symbol; ambiguity never picks a winner."""
    _validate_symbol(symbol)
    if member is not None and (not isinstance(member, str) or not _SYMBOL.fullmatch(member) or "." in member):
        raise ValueError("api_member_invalid")
    index = _index()
    found = index.candidates(symbol)
    if len(found) != 1:
        return {"schema": SCHEMA, "status": "ambiguous" if found else "not_found", "query": symbol, "requested_name": symbol,
                "source_scope": "framework", "sources": [],
                "candidates": [{"symbol": module.name + "." + node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                                "source": _source(module, node), "resolution_sources": trace} for module, node, trace in found[:12]],
                "limitations": ["Lookup covers public packaged source only; not-found is not proof that runtime APIs do not exist."]}
    module, node, trace = found[0]
    return _describe(index, module, node, symbol, member, "framework", trace)


def inspect_python_api(source: str, symbol: str, *, path: str, sha256: str | None = None,
                       member: str | None = None) -> dict:
    """Inspect caller-approved Project source text; never read a supplied path."""
    _validate_symbol(symbol)
    if member is not None and (not isinstance(member, str) or not _SYMBOL.fullmatch(member) or "." in member):
        raise ValueError("api_member_invalid")
    if not isinstance(source, str) or not isinstance(path, str) or len(source.encode("utf-8")) > _MAX_FILE_BYTES:
        raise ValueError("api_source_invalid")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if sha256 is not None and not _SHA.fullmatch(sha256):
        raise ValueError("api_source_digest_invalid")
    # A caller digest may identify exact original file bytes including a BOM;
    # the ProjectSourceRegistry is responsible for that transport envelope.
    module = _Module("project", path, source, sha256 or digest)
    index = _Index({module.name: module})
    local = symbol.rsplit(".", 1)[-1]
    node = module.definitions.get(local)
    if node is None:
        return {"schema": SCHEMA, "status": "not_found", "query": symbol,
                "source_scope": "provided_source", "sources": [], "candidates": [],
                "limitations": ["Only the caller-provided source file was inspected."]}
    return _describe(index, module, node, symbol, member, "provided_source")


def lookup_api_member(result: Mapping, name: str):
    """Return an evidenced member, or None; absence may still be unknown."""
    if not isinstance(result, Mapping) or result.get("status") != "found":
        return None
    selected = result.get("member")
    if isinstance(selected, Mapping) and selected.get("name") == name:
        return dict(selected)
    return next((dict(row) for key in ("methods", "fields") for row in result.get(key, ())
                 if row.get("name") == name), None)


def verify_api_sources(result: Mapping) -> None:
    """Reject stale source evidence; caller data is not an authenticity token."""
    if (not isinstance(result, Mapping) or result.get("schema") != SCHEMA
            or result.get("source_scope") != "framework" or not isinstance(result.get("sources"), list)):
        raise ValueError("api_evidence_invalid")
    for row in result["sources"]:
        if not isinstance(row, Mapping) or not isinstance(row.get("sha256"), str) or not _SHA.fullmatch(row["sha256"]):
            raise ValueError("api_evidence_invalid")
        _, current = _read(row.get("path"))
        if current != row["sha256"]:
            raise ValueError("api_source_changed")
