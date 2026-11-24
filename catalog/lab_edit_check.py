"""Bounded, non-executing checks for a proposed Python source replacement.

This is deliberately not a Python type checker or a sandbox. It checks known
framework receivers and their call shapes against current source declarations.
Unknown receivers, dynamic dispatch, effects and algorithm semantics remain
visible as unchecked work; even an error-free result needs runtime validation.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import inspect
import json
import re


SCHEMA = "nsgablack.python_edit_check/v1"
MAX_SOURCE_BYTES = 48000
MAX_NODES = 6000
MAX_EVIDENCE = 40
MAX_DIAGNOSTICS = 40
MAX_CHECKED_RECORDS = 40
MAX_RESULT_BYTES = 44000
_NAME = re.compile(r"[A-Za-z_]\w*\Z", re.ASCII)
_BINDING = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){0,5}\Z", re.ASCII)
_BUILTINS = {"int", "str", "float", "bool", "complex", "tuple", "list", "dict", "set", "frozenset", "bytes", "NoneType"}
_UNKNOWN = object()


@dataclass(frozen=True)
class _Value:
    symbol: str = ""
    kind: str = "unknown"  # instance / symbol / module / method / builtin / external / invalid
    member: dict | None = None
    owner: dict | None = None
    bound: bool = False


def _annotation(node):
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


class _Checker:
    def __init__(self, bindings):
        self.bindings = bindings
        self.evidence = {}
        self.aliases = {}
        self.members = {}
        self.module_paths = set()
        self.diagnostics = []
        self.calls = []
        self.fields = []
        self.unresolved = []
        self._seen = set()
        self._lookup_limit = False
        self.has_errors = False
        self.truncated = False
        self.scope = []

    def _note(self, node, code, message, *, severity="unknown", symbol=None):
        key = (getattr(node, "lineno", 1), getattr(node, "col_offset", 0), code, symbol)
        if key in self._seen:
            return
        self._seen.add(key)
        row = {"code": code, "severity": severity, "line": key[0], "column": key[1] + 1,
               "message": message}
        if symbol:
            row["symbol"] = symbol
        if severity == "error":
            self.has_errors = True
        if len(self.diagnostics) < MAX_DIAGNOSTICS:
            self.diagnostics.append(row)
        else:
            self.truncated = True
            if severity == "error":
                replace = next((i for i in range(len(self.diagnostics) - 1, -1, -1)
                                if self.diagnostics[i]["severity"] != "error"), None)
                if replace is not None:
                    self.diagnostics[replace] = row
        if severity == "unknown" and len(self.unresolved) < MAX_DIAGNOSTICS:
            self.unresolved.append(row.copy())

    def api(self, symbol, node):
        symbol = self.aliases.get(symbol, symbol)
        if symbol in self.evidence:
            return self.evidence[symbol]
        if len(self.evidence) >= MAX_EVIDENCE:
            self._lookup_limit = True
            self._note(node, "api_check_budget_exceeded", "Further API receivers were not checked.")
            return None
        from .lab_api import inspect_framework_api
        try:
            result = inspect_framework_api(symbol)
        except (ValueError, OSError, TypeError):
            self._note(node, "api_lookup_unresolved", "The current source declaration could not be resolved.", symbol=symbol)
            return None
        key = result.get("symbol", symbol) if result.get("status") == "found" else symbol
        self.evidence[key] = result
        self.aliases[symbol] = key
        if result.get("status") != "found":
            self._note(node, "api_lookup_unresolved", "The framework symbol is absent or ambiguous in the source index.", symbol=symbol)
            return None
        return result

    def typed(self, annotation, env):
        """Infer only unambiguous named types, never evaluate annotations."""
        if not annotation:
            return _Value()
        try:
            node = ast.parse(annotation, mode="eval").body
        except (SyntaxError, ValueError):
            return _Value()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return self.typed(node.value, env)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            if isinstance(node.right, ast.Constant) and node.right.value is None:
                node = node.left
            elif isinstance(node.left, ast.Constant) and node.left.value is None:
                node = node.right
            else:
                return _Value()
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Optional":
            node = node.slice
        if isinstance(node, ast.Subscript):
            root = ast.unparse(node.value).removeprefix("typing.")
            builtin = {"Tuple": "tuple", "List": "list", "Dict": "dict", "Set": "set", "FrozenSet": "frozenset"}.get(root, root)
            if builtin in _BUILTINS:
                return _Value("builtins." + builtin, "builtin")
        if isinstance(node, ast.Name):
            value = env.get(node.id)
            if value and value.kind == "symbol":
                return _Value(value.symbol, "instance")
            if node.id in _BUILTINS:
                return _Value("builtins." + node.id, "builtin")
            # API annotations often use a same-module class without importing
            # it in the proposed source. A unique source lookup is required.
            if node.id not in {"Any", "Self", "None", "int", "str", "float", "bool", "tuple", "list", "dict", "set", "object"}:
                result = self.api(node.id, node)
                if result and result.get("kind") == "class":
                    return _Value(result["symbol"], "instance")
        if isinstance(node, ast.Attribute):
            dotted = ast.unparse(node)
            root = dotted.split(".")[0]
            value = env.get(root)
            if value and value.kind == "module":
                return _Value(value.symbol + dotted[len(root):], "instance")
        return _Value()

    def returned(self, item, env):
        inferred = item.get("return_contract", {})
        if inferred.get("kind") in {"instance", "builtin"} and inferred.get("symbol"):
            return _Value(inferred["symbol"], inferred["kind"], item)
        return self.typed(item.get("returns", item.get("annotation", "")), env)

    def _member(self, receiver, name, node):
        from .lab_api import inspect_framework_api, lookup_api_member
        api = self.api(receiver.symbol, node)
        if not api:
            return _Value()
        member_key = (api["symbol"], name)
        item = self.members.get(member_key, _UNKNOWN)
        if item is _UNKNOWN:
            item = lookup_api_member(api, name)
        if ((item is None and name in api.get("member_names", ())) or
                (item and "parameters" in item and not item.get("returns") and "return_contract" not in item)):
            # Full listings are bounded; exact lookup resolves an omitted body.
            evidence_key = api["symbol"] + "." + name
            specific = self.evidence.get(evidence_key)
            if specific is None:
                if len(self.evidence) >= MAX_EVIDENCE:
                    self._note(node, "api_check_budget_exceeded", "Further API members were not checked.")
                    return _Value()
                specific = inspect_framework_api(receiver.symbol, member=name)
            self.evidence[evidence_key] = specific
            item = specific.get("member")
        self.members[member_key] = item
        if item is None:
            complete = api.get("members_complete", False)
            if complete and not api.get("dynamic_attributes") and not api.get("unresolved_bases"):
                self._note(node, "api_member_missing", "The declared receiver does not provide this member.",
                           severity="error", symbol=api["symbol"] + "." + name)
                return _Value(kind="invalid")
            self._note(node, "api_member_undeclared", "This member is not declared; dynamic or unresolved bases prevent proving absence.",
                       symbol=api["symbol"] + "." + name)
            return _Value()
        kind = item.get("kind")
        if "parameters" in item and kind != "property":
            return _Value(api["symbol"] + "." + name, "method", item, api,
                          receiver.kind == "instance" or kind == "classmethod")
        if len(self.fields) < MAX_CHECKED_RECORDS:
            self.fields.append({"line": node.lineno, "symbol": api["symbol"] + "." + name,
                                "source": item.get("source")})
        else:
            self.truncated = True
        return self.returned(item, {})

    def numeric_coercion(self, node, arguments, env):
        dtype = next((kw.value for kw in node.keywords if kw.arg == "dtype"), node.args[1] if len(node.args) > 1 else None)
        numeric = (isinstance(dtype, ast.Name) and dtype.id in {"float", "int", "complex"} and dtype.id not in env)
        if not numeric or not arguments or arguments[0].kind != "instance":
            return
        api = self.api(arguments[0].symbol, node)
        protocols = {"__array__", "__array_interface__", "__array_struct__", "__iter__", "__getitem__",
                     "__float__", "__int__", "__index__", "__complex__"}
        if (api and api.get("members_complete") and not api.get("dynamic_attributes")
                and not api.get("unresolved_bases") and not protocols.intersection(api.get("member_names", ()))):
            self._note(node, "api_numeric_coercion_invalid", "The resolved framework object declares no numeric, array or sequence conversion protocol. Inspect its value access API before numeric conversion.",
                       severity="error", symbol=api["symbol"])

    def expr(self, node, env):
        if node is None:
            return _Value()
        if isinstance(node, ast.Name):
            return env.get(node.id, _Value())
        if isinstance(node, ast.NamedExpr):
            value = self.expr(node.value, env)
            self.assign(node.target, value, env)
            return value
        if isinstance(node, ast.Attribute):
            receiver = self.expr(node.value, env)
            if receiver.kind == "external":
                return _Value(receiver.symbol + "." + node.attr, "external")
            if receiver.kind == "module":
                candidate = receiver.symbol + "." + node.attr
                return _Value(candidate, "module" if candidate in self.module_paths else "symbol")
            if receiver.kind in {"instance", "symbol"}:
                # Imported classes are only inspected here if used as class
                # receivers. Module traversal is kept as a dotted import path.
                api = self.api(receiver.symbol, node)
                if receiver.kind == "symbol" and api and api.get("kind") != "class":
                    return _Value(receiver.symbol + "." + node.attr, "symbol")
                return self._member(receiver, node.attr, node)
            if receiver.kind != "invalid":
                self._note(node, "attribute_receiver_unresolved", "Receiver type is unknown; this attribute was not checked.")
            return _Value(kind="invalid" if receiver.kind == "invalid" else "unknown")
        if isinstance(node, ast.Call):
            target = self.expr(node.func, env)
            arguments = [self.expr(argument, env) for argument in node.args]
            for keyword in node.keywords:
                self.expr(keyword.value, env)
            if isinstance(node.func, ast.Name) and node.func.id in {"getattr", "setattr", "delattr", "eval", "exec", "__import__"}:
                self._note(node, "dynamic_operation_unchecked", "Dynamic lookup or execution cannot be verified by this source checker.")
                return _Value()
            if target.kind == "method":
                self.check_call(node, target.member, target.symbol, bound=target.bound)
                return self.returned(target.member, env)
            if target.kind == "builtin":
                self._note(node, "api_noncallable_value_called", "This expression resolves to a non-callable value, not a method. Read it as a value rather than invoking it.",
                           severity="error", symbol=target.symbol)
                return _Value(kind="invalid")
            if target.kind == "external" and target.symbol in {"numpy.array", "numpy.asarray"}:
                self.numeric_coercion(node, arguments, env)
            if target.kind == "symbol":
                api = self.api(target.symbol, node)
                if api:
                    if api.get("kind") == "class":
                        from .lab_api import lookup_api_member
                        init = lookup_api_member(api, "__init__")
                        if init:
                            self.check_call(node, init, api["symbol"], bound=True)
                        else:
                            self._note(node, "constructor_signature_unresolved", "The constructor is generated or not statically declared; its arguments were not checked.", symbol=api["symbol"])
                        return _Value(api["symbol"], "instance")
                    item = api.get("member") or api
                    if "parameters" in item:
                        self.check_call(node, item, api["symbol"], bound=False)
                        return self.returned(item, env)
            if target.kind != "invalid":
                self._note(node, "call_target_unresolved", "This call target is not a resolved framework API; runtime validation is required.")
            return _Value()
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            nested = dict(env)
            for generator in node.generators:
                self.expr(generator.iter, nested)
                self.assign(generator.target, _Value(), nested)
                for condition in generator.ifs:
                    self.expr(condition, nested)
            if isinstance(node, ast.DictComp):
                self.expr(node.key, nested)
                self.expr(node.value, nested)
            else:
                self.expr(node.elt, nested)
            return _Value()
        if isinstance(node, ast.Lambda):
            nested = dict(env)
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                nested[arg.arg] = _Value()
            self.expr(node.body, nested)
            return _Value()
        for child in ast.iter_child_nodes(node):
            self.expr(child, env)
        return _Value()

    def check_call(self, node, method, symbol, *, bound):
        parameters = []
        kinds = {"positional_only": inspect.Parameter.POSITIONAL_ONLY,
                 "positional_or_keyword": inspect.Parameter.POSITIONAL_OR_KEYWORD,
                 "keyword_only": inspect.Parameter.KEYWORD_ONLY,
                 "var_positional": inspect.Parameter.VAR_POSITIONAL,
                 "var_keyword": inspect.Parameter.VAR_KEYWORD}
        declared = list(method.get("parameters", ()))
        if bound and method.get("kind") != "staticmethod" and declared and declared[0]["name"] in {"self", "cls"}:
            declared.pop(0)
        for parameter in declared:
            kind = kinds[parameter["kind"]]
            default = inspect.Parameter.empty
            if kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD} and not parameter["required"]:
                default = _UNKNOWN
            parameters.append(inspect.Parameter(parameter["name"], kind, default=default))
        if any(isinstance(arg, ast.Starred) for arg in node.args) or any(kw.arg is None for kw in node.keywords):
            self._note(node, "call_unpacking_unchecked", "Starred arguments prevent checking the complete call shape.", symbol=symbol)
            return
        try:
            signature = inspect.Signature(parameters)
            signature.bind(*[_UNKNOWN for _ in node.args], **{kw.arg: _UNKNOWN for kw in node.keywords})
        except (TypeError, ValueError) as exc:
            self._note(node, "api_call_signature_invalid", str(exc), severity="error", symbol=symbol)
            return
        if len(self.calls) < MAX_CHECKED_RECORDS:
            self.calls.append({"line": node.lineno, "symbol": symbol, "signature": method.get("signature"),
                               "source": method.get("source"), "checked_scope": "signature_only"})
        else:
            self.truncated = True

    def assign(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            for member in target.elts:
                self.assign(member, _Value(), env)
        else:
            # Mutating an attribute is an effect; a declared field name alone
            # cannot establish whether assignment is permitted by its owner.
            self.expr(target, env)
            self._note(target, "assignment_effect_unchecked", "Assignment effects and field mutability require runtime validation.")

    def statements(self, body, env):
        for node in body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if node.module and node.module.startswith("nsgablack") and alias.name != "*":
                        env[name] = _Value(node.module + "." + alias.name, "symbol")
                    elif node.module == "numpy" and alias.name != "*":
                        env[name] = _Value(node.module + "." + alias.name, "external")
                    else:
                        env[name] = _Value()
                        if alias.name == "*":
                            self._note(node, "wildcard_import_unchecked", "Wildcard import names cannot be bound statically here.")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if alias.name.startswith("nsgablack"):
                        parts = alias.name.split(".")
                        self.module_paths.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
                    env[name] = (_Value(alias.name if alias.asname else name, "module") if alias.name.startswith("nsgablack") else
                                 _Value("numpy", "external") if alias.name == "numpy" else _Value())
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nested = dict(env)
                # Python decides local names for the whole function, even
                # before the assignment. Do not reuse an outer receiver for a
                # local name whose value has not yet been assigned.
                for local in _local_names(node.body):
                    nested[local] = _Value()
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    inferred = self.typed(_annotation(arg.annotation), env)
                    supplied = self.bindings.get(".".join((*self.scope, node.name, arg.arg)), self.bindings.get(arg.arg))
                    if supplied and inferred.kind == "unknown":
                        inferred = _Value(supplied, "instance")
                    elif supplied and inferred.kind == "instance":
                        given = self.api(supplied, arg)
                        actual = self.api(inferred.symbol, arg)
                        if given and actual and given["symbol"] != actual["symbol"]:
                            self._note(arg, "binding_annotation_conflict", "An explicit receiver binding contradicts the source annotation.", severity="error")
                    nested[arg.arg] = inferred
                for arg in (node.args.vararg, node.args.kwarg):
                    if arg:
                        nested[arg.arg] = _Value()
                for default in (*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)):
                    self.expr(default, env)
                for decorator in node.decorator_list:
                    self.expr(decorator, env)
                self.scope.append(node.name)
                self.statements(node.body, nested)
                self.scope.pop()
                env[node.name] = _Value()
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    self.expr(base, env)
                for decorator in node.decorator_list:
                    self.expr(decorator, env)
                self.scope.append(node.name)
                self.statements(node.body, dict(env))
                self.scope.pop()
                env[node.name] = _Value()
            elif isinstance(node, ast.Assign):
                value = self.expr(node.value, env)
                for target in node.targets:
                    self.assign(target, value, env)
            elif isinstance(node, ast.AnnAssign):
                value = self.expr(node.value, env)
                declared = self.typed(_annotation(node.annotation), env)
                self.assign(node.target, declared if declared.kind != "unknown" else value, env)
            elif isinstance(node, ast.AugAssign):
                self.expr(node.value, env)
                self.expr(node.target, env)
                self.assign(node.target, _Value(), env)
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    self.assign(target, _Value(), env)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                self.expr(node.iter, env)
                branch = dict(env)
                self.assign(node.target, _Value(), branch)
                self.statements(node.body, branch)
                for name in set(env) | set(branch):
                    env[name] = env.get(name, _Value()) if env.get(name) == branch.get(name) else _Value()
                self.statements(node.orelse, env)
            elif isinstance(node, ast.While):
                self.expr(node.test, env)
                branch = dict(env)
                self.statements(node.body, branch)
                for name in set(env) | set(branch):
                    if env.get(name) != branch.get(name):
                        env[name] = _Value()
                self.statements(node.orelse, env)
            elif isinstance(node, ast.If):
                self.expr(node.test, env)
                left, right = dict(env), dict(env)
                self.statements(node.body, left)
                self.statements(node.orelse, right)
                for name in set(left) | set(right):
                    env[name] = left.get(name, _Value()) if left.get(name) == right.get(name) else _Value()
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    self.expr(item.context_expr, env)
                    if item.optional_vars:
                        self.assign(item.optional_vars, _Value(), env)
                self.statements(node.body, env)
            elif isinstance(node, ast.Try):
                branches = []
                for block, exception_name in [(node.body, None), (node.orelse, None), (node.finalbody, None),
                                              *((handler.body, handler.name) for handler in node.handlers)]:
                    branch = dict(env)
                    if exception_name:
                        branch[exception_name] = _Value()
                    self.statements(block, branch)
                    branches.append(branch)
                for name in set().union(*(set(branch) for branch in branches)):
                    values = [branch.get(name, _Value()) for branch in branches]
                    env[name] = values[0] if all(item == values[0] for item in values) else _Value()
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                for name in node.names:
                    env[name] = _Value()
                self._note(node, "nonlocal_binding_unchecked", "Global and nonlocal receiver values are not inferred.")
            elif isinstance(node, ast.Match):
                self.expr(node.subject, env)
                self._note(node, "pattern_binding_unchecked", "Pattern-bound receiver types are not inferred.")
                # Pattern captures can shadow known names in the enclosing
                # scope. Avoid retaining any such receiver as verified.
                for name in env:
                    env[name] = _Value()
                for case in node.cases:
                    branch = dict(env)
                    self.expr(case.guard, branch)
                    self.statements(case.body, branch)
            else:
                self.expr(node, env)


def _local_names(body):
    names = set()
    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            return
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        for child in ast.iter_child_nodes(node):
            visit(child)
    for statement in body:
        visit(statement)
    return names


def check_python_edit(source: str, *, bindings: Mapping[str, str] | None = None) -> dict:
    """Check current declared API use without importing or running the proposal.

    ``bindings`` are explicit caller type assumptions for otherwise untyped
    parameters. A dotted ``function.parameter`` (or class/nested function path)
    limits the assumption to that lexical scope; simple names retain the legacy
    all-scope behavior. Neither form proves runtime types; both remain reported.
    No successful result is a semantic, effect, or execution certificate.
    """
    if not isinstance(source, str) or not 0 < len(source.encode("utf-8")) <= MAX_SOURCE_BYTES:
        raise ValueError("edit_source_invalid")
    if bindings is None:
        bindings = {}
    if (not isinstance(bindings, Mapping) or len(bindings) > 24 or any(
            not isinstance(name, str) or len(name) > 240 or not _BINDING.fullmatch(name) or not isinstance(symbol, str)
            or not 1 <= len(symbol) <= 240 for name, symbol in bindings.items())):
        raise ValueError("edit_bindings_invalid")
    report = {"schema": SCHEMA, "code_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
              "syntax_ok": False, "status": "rejected", "diagnostics": [], "checked_calls": [],
              "checked_fields": [], "unresolved": [], "api_evidence": [],
              "binding_assumptions": dict(bindings), "execution_status": "not_run", "report_truncated": False,
              "limitations": ["Checks only resolved framework API declarations and call shapes; does not execute or apply source.",
                              "Supplied receiver bindings are assumptions, not evidence of runtime object types.",
                              "Unknown/dynamic calls, side effects, types of values, formulas and algorithm semantics require further validation."]}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        report["diagnostics"] = [{"code": "edit_syntax_invalid", "severity": "error", "line": getattr(exc, "lineno", 1),
                                  "column": getattr(exc, "offset", 1), "message": "The proposed source is not valid Python."}]
        return report
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ValueError("edit_source_too_complex")
    try:
        # Compilation catches duplicate keywords and invalid control placement
        # that ast.parse accepts. The resulting code object is never executed.
        compile(tree, "<proposed_edit>", "exec", dont_inherit=True)
    except (SyntaxError, ValueError) as exc:
        report["diagnostics"] = [{"code": "edit_syntax_invalid", "severity": "error", "line": getattr(exc, "lineno", 1),
                                  "column": getattr(exc, "offset", 1), "message": "The proposed source cannot compile as a Python module."}]
        return report
    report["syntax_ok"] = True
    checker = _Checker(dict(bindings))
    # Validate explicit names before any lookup can interpret a path-like value.
    for name, symbol in bindings.items():
        value = checker.api(symbol, tree)
        if value and value.get("kind") != "class":
            checker._note(tree, "receiver_binding_not_class", "A receiver binding must resolve to a class declaration.", severity="error", symbol=symbol)
    checker.statements(tree.body, {name: _Value(symbol, "instance") for name, symbol in bindings.items() if "." not in name})
    from .lab_api import verify_api_sources
    for evidence in checker.evidence.values():
        try:
            verify_api_sources(evidence)
        except (OSError, TypeError, ValueError):
            checker._note(tree, "api_source_changed", "API source changed during checking; regenerate against the current source.", severity="error")
    # Keep hashes and exact locations, not repeated whole-class listings. The
    # reader can request full API detail separately through the same inspector.
    sources = {}
    for evidence in checker.evidence.values():
        for row in evidence.get("sources", ()):
            sources[(row["path"], row["sha256"])] = row
    report.update(diagnostics=checker.diagnostics, checked_calls=checker.calls,
                  checked_fields=checker.fields, unresolved=checker.unresolved,
                  api_evidence=[{"schema": "nsgablack.lab_api/v1", "source_scope": "framework",
                                 "sources": list(sources.values())}], report_truncated=checker.truncated)
    report["status"] = "rejected" if checker.has_errors else "needs_runtime_validation"
    while len(json.dumps(report, ensure_ascii=False).encode("utf-8")) > MAX_RESULT_BYTES:
        report["report_truncated"] = True
        if report["checked_calls"]:
            report["checked_calls"].pop()
        elif report["checked_fields"]:
            report["checked_fields"].pop()
        elif report["unresolved"]:
            report["unresolved"].pop()
        else:
            raise ValueError("edit_evidence_too_large")
    return report
