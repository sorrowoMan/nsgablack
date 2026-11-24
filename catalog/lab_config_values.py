"""Evaluate a small, explicit subset of configuration expressions without exec.

This reads declared values and property arithmetic. It does not construct the
configuration class, run validators, or interpret general Python.
"""
from __future__ import annotations

import ast
import hashlib
import math
import operator


def calculate_config_values(source, symbol, *, values=None, properties=()):
    if (not isinstance(source, str) or len(source.encode()) > 128_000
            or not isinstance(symbol, str) or not symbol.isidentifier()
            or values is not None and not isinstance(values, dict) or len(values or {}) > 40
            or not isinstance(properties, (list, tuple)) or len(properties) > 12
            or any(not isinstance(name, str) for name in properties)):
        raise ValueError("config_expression_request_invalid")
    tree = ast.parse(source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == symbol]
    if len(classes) != 1:
        raise ValueError("config_class_not_found")
    cls = classes[0]
    defaults = {n.target.id: n for n in cls.body if isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name) and not n.target.id.startswith("_")}
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)
               and any(isinstance(d, ast.Name) and d.id == "property" for d in n.decorator_list)}
    if set(values or {}) - defaults.keys() or any(name not in methods for name in properties):
        raise ValueError("config_member_unknown")
    fields, cache, visiting = {}, {}, set()
    remaining = 500
    binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
    comparisons = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                   ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                   ast.Is: operator.is_, ast.IsNot: operator.is_not}

    def bounded(value):
        if (type(value) is int and abs(value) > 10**15
                or type(value) is float and (not math.isfinite(value) or abs(value) > 10**15)):
            raise ValueError("config_value_out_of_bounds")
        if type(value) not in (str, int, float, bool, type(None), tuple, list):
            raise ValueError("config_value_unsupported")
        if isinstance(value, (str, tuple, list)) and len(value) > 128:
            raise ValueError("config_value_out_of_bounds")
        if isinstance(value, (tuple, list)):
            for item in value:
                bounded(item)
        return value

    def expr(node, local):
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise ValueError("config_expression_budget_exceeded")
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            return bounded([expr(n, local) for n in node.elts])
        if isinstance(node, ast.Name) and node.id in local:
            return local[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
            return resolve(node.attr)
        if isinstance(node, ast.IfExp):
            return expr(node.body if expr(node.test, local) else node.orelse, local)
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            left, right = expr(node.left, local), expr(node.right, local)
            # Only numeric arithmetic: reject string/list amplification.
            if type(left) not in (int, float) or type(right) not in (int, float):
                raise ValueError("config_arithmetic_not_numeric")
            return bounded(binary[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = expr(node.operand, local)
            return bounded(not value if isinstance(node.op, ast.Not) else
                           +value if isinstance(node.op, ast.UAdd) else -value)
        if isinstance(node, ast.Compare):
            left = expr(node.left, local)
            for op, other in zip(node.ops, node.comparators):
                if type(op) not in comparisons:
                    raise ValueError("config_expression_unsupported")
                right = expr(other, local)
                if not comparisons[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            for child in node.values:
                value = expr(child, local)
                if isinstance(node.op, ast.And) and not value or isinstance(node.op, ast.Or) and value:
                    return value
            return value
        raise ValueError("config_expression_unsupported")

    def statements(nodes, local):
        for node in nodes:
            if isinstance(node, ast.Return):
                return expr(node.value, local)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                local[node.targets[0].id] = expr(node.value, local)
            elif isinstance(node, ast.If):
                return statements(node.body if expr(node.test, local) else node.orelse, local)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            else:
                raise ValueError("config_statement_unsupported")
        raise ValueError("config_return_missing")

    def resolve(name):
        if name in cache:
            return cache[name]
        if name in fields:
            return fields[name]
        if name in visiting or len(visiting) >= 8:
            raise ValueError("config_property_cycle")
        visiting.add(name)
        try:
            if name in defaults:
                value = expr(defaults[name].value, {})
                fields[name] = value
            elif name in methods:
                value = statements(methods[name].body, {})
                cache[name] = bounded(value)
            else:
                raise ValueError("config_dependency_unknown")
            return value
        finally:
            visiting.remove(name)

    for name, value in (values or {}).items():
        value = bounded(value)
        annotation = ast.unparse(defaults[name].annotation)
        if annotation in {"int", "float", "str", "bool"}:
            allowed = {"int": (int,), "float": (int, float), "str": (str,), "bool": (bool,)}[annotation]
            if type(value) not in allowed:
                raise ValueError("config_value_type_invalid")
        fields[name] = value
    results, unsupported = {}, []
    for name in properties:
        try:
            results[name] = resolve(name)
        except (ValueError, TypeError, ArithmeticError):
            unsupported.append(name)
    return {"schema": "nsgablack.config_expression_values/v1", "symbol": symbol,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "inputs": values or {}, "properties": results, "unsupported": unsupported,
            "status": "computed" if not unsupported else "incomplete",
            "limitations": ["Only the supported literal/property arithmetic was evaluated; no module was imported.",
                            "Class construction, __post_init__, validation and runtime budget consumption were not executed."]}
