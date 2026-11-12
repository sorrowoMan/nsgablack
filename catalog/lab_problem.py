"""Declarative numerical Problems for the private assembly workbench.

Expressions are interpreted by walking a small arithmetic AST.  They never
become Python code.  The same module is copied into exported formal Cases,
and is used by the result verifier: there is one definition of the semantics.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import lru_cache
import json
import math
from pathlib import Path
import re

import numpy as np

from nsgablack.core import BlackBoxProblem
from nsgablack.representation.continuous import UniformInitializer

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z")
_FUNCTIONS = {"abs": abs, "min": min, "max": max, "sqrt": math.sqrt,
              "log": math.log, "exp": math.exp, "sin": math.sin, "cos": math.cos}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_PRESETS = {"problem.two_centers": 2, "problem.sphere": 1}
_MAX_MAGNITUDE = 1e100


def _object(value, allowed, label):
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise ValueError(f"{label} 必须是字符串键的对象")
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(f"{label} 不支持字段：{', '.join(sorted(extra))}")
    return dict(value)


def _number(value, label, *, low=-1e6, high=1e6):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f"{label} 必须是 {low:g}..{high:g} 内的有限数值")
    return float(value)


def _label(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 80 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} 必须是 1..80 个可显示字符")
    return value.strip()


def _dimension(value):
    if type(value) is not int or not 1 <= value <= 8:
        raise ValueError("问题维度必须为 1..8")
    return value


def _exponent(node):
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if not isinstance(node, ast.Constant) or type(node.value) is not int or abs(node.value) > 12:
        raise ValueError("幂指数必须是 -12..12 的整数字面量")
    return sign * node.value


@lru_cache(maxsize=256)
def _expression_tree(expression, names):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 512:
        raise ValueError("公式必须为 1..512 字符的算术表达式")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise ValueError("公式不是有效的算术表达式") from exc
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("公式超过 128 个语法节点")

    def check(node, depth=0):
        if depth > 24:
            raise ValueError("公式嵌套超过 24 层")
        if isinstance(node, ast.Expression):
            check(node.body, depth + 1)
        elif isinstance(node, ast.Constant):
            _number(node.value, "公式常数")
        elif isinstance(node, ast.Name):
            if node.id not in names and node.id not in _CONSTANTS:
                raise ValueError(f"公式引用了未声明变量：{node.id}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)):
            check(node.left, depth + 1)
            if isinstance(node.op, ast.Pow):
                _exponent(node.right)
            check(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            check(node.operand, depth + 1)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
            if node.keywords or not (1 <= len(node.args) <= 8 if node.func.id in {"min", "max"} else len(node.args) == 1):
                raise ValueError(f"{node.func.id} 的参数数量不正确或包含关键字")
            if node.func.id in {"min", "max"} and len(node.args) < 2:
                raise ValueError("min/max 至少需要两个数值参数")
            for item in node.args:
                check(item, depth + 1)
        else:
            raise ValueError("公式只支持数值、已声明变量、算术与允许的数学函数；不支持 Python 代码")

    check(tree)
    return tree.body


def _formula(value, names):
    if not isinstance(value, str):
        raise ValueError("公式必须是算术表达式字符串")
    _expression_tree(value, names)
    return value.strip()


def normalize_problem(binding, dimension=None):
    """Return detached canonical data; do not instantiate a Problem or evaluate it."""
    raw = _object(binding, {"component", "parameters"}, "problem")
    key = raw.get("component")
    if not isinstance(key, str):
        raise ValueError("problem.component 必须是已支持的问题组件名称")
    if key in _PRESETS:
        _object(raw.get("parameters", {}), set(), "预设问题参数")
        if dimension is not None:
            _dimension(dimension)
        return {"component": key, "parameters": {}}
    if key != "problem.expression":
        raise ValueError("实验台问题只支持声明式公式或已登记预设；外部评估须正式 Provider")
    params = _object(raw.get("parameters", {}), {"variables", "objectives", "constraints"}, "公式问题参数")
    variables = params.get("variables")
    if not isinstance(variables, list) or not 1 <= len(variables) <= 8:
        raise ValueError("公式问题需要明确声明 1..8 个连续变量及边界")
    if dimension is not None and _dimension(dimension) != len(variables):
        raise ValueError("dimension 必须等于问题变量数量")
    normalized_variables = []
    for item in variables:
        row = _object(item, {"name", "low", "high", "type"}, "变量")
        name = row.get("name")
        if (not isinstance(name, str) or not _NAME.fullmatch(name)
                or name in _FUNCTIONS or name in _CONSTANTS):
            raise ValueError("变量名须为字母开头的 1..32 位 ASCII 字母数字下划线，且不能与数学函数/常数同名")
        if row.get("type", "continuous") != "continuous":
            raise ValueError("本实验台绑定只支持连续变量；不把连续算法伪装成整数/类别搜索")
        low, high = _number(row.get("low"), name + " 下界"), _number(row.get("high"), name + " 上界")
        if low >= high:
            raise ValueError(f"{name} 下界必须严格小于上界")
        normalized_variables.append(dict(name=name, low=low, high=high, type="continuous"))
    names = tuple(v["name"] for v in normalized_variables)
    if len(set(names)) != len(names):
        raise ValueError("变量名不能重复")
    objectives = params.get("objectives")
    if not isinstance(objectives, list) or not 1 <= len(objectives) <= 2:
        raise ValueError("公式问题需要明确声明 1..2 个目标")
    normalized_objectives = []
    for item in objectives:
        row = _object(item, {"name", "expression", "direction"}, "目标")
        if row.get("direction") not in {"min", "max"}:
            raise ValueError("每个目标必须明确 direction=min 或 max")
        normalized_objectives.append(dict(name=_label(row.get("name"), "目标名称"),
            expression=_formula(row.get("expression"), names), direction=row["direction"]))
    if len({r["name"] for r in normalized_objectives}) != len(normalized_objectives):
        raise ValueError("目标名称不能重复")
    constraints = params.get("constraints", [])
    if not isinstance(constraints, list) or len(constraints) > 8:
        raise ValueError("公式问题最多声明 8 条约束")
    normalized_constraints = []
    for item in constraints:
        row = _object(item, {"name", "expression", "relation", "rhs", "tolerance"}, "约束")
        if row.get("relation") not in {"<=", ">=", "=="}:
            raise ValueError("约束须明确 relation 为 <=、>= 或 ==")
        normalized_constraints.append(dict(name=_label(row.get("name"), "约束名称"),
            expression=_formula(row.get("expression"), names), relation=row["relation"],
            rhs=_number(row.get("rhs"), "约束右值"),
            tolerance=_number(row.get("tolerance", 0.), "约束绝对容差", low=0.)))
    if len({r["name"] for r in normalized_constraints}) != len(normalized_constraints):
        raise ValueError("约束名称不能重复")
    return dict(component=key, parameters=dict(variables=normalized_variables,
        objectives=normalized_objectives, constraints=normalized_constraints))


def problem_bounds(binding, dimension=None):
    normalized = normalize_problem(binding, dimension)
    if normalized["component"] == "problem.expression":
        return [(v["low"], v["high"]) for v in normalized["parameters"]["variables"]]
    return [(-2., 2.)] * _dimension(2 if dimension is None else dimension)


def objective_count(binding):
    normalized = normalize_problem(binding)
    if normalized["component"] in _PRESETS:
        return _PRESETS[normalized["component"]]
    return len(normalized["parameters"]["objectives"])


def objective_definitions(binding):
    normalized = normalize_problem(binding)
    if normalized["component"] == "problem.expression":
        return normalized["parameters"]["objectives"]
    names = ["left", "right"] if normalized["component"] == "problem.two_centers" else ["squared_norm"]
    return [dict(name=name, direction="min") for name in names]


def display_objectives(binding, algorithm_values):
    """Restore user directions; raw algorithm feedback remains a minimization view."""
    definitions = objective_definitions(binding)
    if not isinstance(algorithm_values, (list, tuple, np.ndarray)) or len(algorithm_values) != len(definitions):
        raise ValueError("目标显示值数量与问题定义不一致")
    return [float(value) * (-1. if row["direction"] == "max" else 1.)
            for row, value in zip(definitions, algorithm_values)]


def _calculate(node, values):
    if isinstance(node, ast.Constant):
        result = node.value
    elif isinstance(node, ast.Name):
        result = values[node.id] if node.id in values else _CONSTANTS[node.id]
    elif isinstance(node, ast.UnaryOp):
        result = _calculate(node.operand, values)
        if isinstance(node.op, ast.USub):
            result = -result
    elif isinstance(node, ast.BinOp):
        left, right = _calculate(node.left, values), _calculate(node.right, values)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        elif isinstance(node.op, ast.Div):
            result = left / right
        elif isinstance(node.op, ast.Mod):
            result = left % right
        else:
            result = left ** int(right)
    else:
        result = _FUNCTIONS[node.func.id](*(_calculate(a, values) for a in node.args))
    if isinstance(result, complex) or not math.isfinite(result) or abs(result) > _MAX_MAGNITUDE:
        raise ValueError("公式产生非有限或过大数值")
    return float(result)


def _evaluate_expression(text, names, values, label):
    try:
        return _calculate(_expression_tree(text, names), values)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError(f"{label} 求值失败：请检查定义域、分母和数值尺度") from exc


def _candidate(binding, candidate):
    x = np.asarray(candidate, dtype=float)
    if x.ndim != 1 or not 1 <= len(x) <= 8 or not np.all(np.isfinite(x)):
        raise ValueError("候选必须为与问题变量对齐的有限一维数值")
    normalized = normalize_problem(binding, len(x))
    return normalized, x


def _constraint_values(normalized, x):
    bounds = problem_bounds(normalized, len(x))
    # Core constraint evaluation sums positive values and does not add bounds.
    result = [max(low - float(value), 0., float(value) - high)
              for value, (low, high) in zip(x, bounds)]
    if normalized["component"] == "problem.expression":
        params = normalized["parameters"]
        names = tuple(v["name"] for v in params["variables"])
        values = dict(zip(names, map(float, x)))
        for row in params["constraints"]:
            left = _evaluate_expression(row["expression"], names, values, row["name"])
            delta = left - row["rhs"]
            if row["relation"] == ">=":
                delta = -delta
            elif row["relation"] == "==":
                delta = abs(delta)
            result.append(max(delta - row["tolerance"], 0.))
    return result


def evaluate_problem(binding, candidate):
    """Return raw minimization objectives and total nonnegative hard violation."""
    normalized, x = _candidate(binding, candidate)
    key = normalized["component"]
    if key == "problem.sphere":
        objectives = [float(np.sum(x ** 2))]
    elif key == "problem.two_centers":
        left, right = np.zeros(len(x)), np.zeros(len(x))
        left[0], right[0] = -1., 1.
        objectives = [float(np.sum((x - left) ** 2)), float(np.sum((x - right) ** 2))]
    else:
        params = normalized["parameters"]
        names = tuple(v["name"] for v in params["variables"])
        values = dict(zip(names, map(float, x)))
        objectives = [(-1. if row["direction"] == "max" else 1.) *
            _evaluate_expression(row["expression"], names, values, row["name"])
            for row in params["objectives"]]
    return objectives, float(sum(_constraint_values(normalized, x)))


class LabProblem(BlackBoxProblem):
    """A real optimization Problem; maximization is represented as -f(x)."""
    def __init__(self, dimension, binding):
        self.binding = normalize_problem(binding, dimension)
        super().__init__(name="lab_" + self.binding["component"].split(".")[-1],
            dimension=dimension, bounds=problem_bounds(self.binding, dimension),
            objectives=[row["name"] for row in objective_definitions(self.binding)])
        if self.binding["component"] == "problem.expression":
            self.variables = [row["name"] for row in self.binding["parameters"]["variables"]]

    def evaluate(self, candidate):
        # Evaluate constraints here too, so a formula-domain error propagates
        # before generic constraint helpers can downgrade it to +inf.
        return evaluate_problem(self.binding, candidate)[0]

    def evaluate_constraints(self, candidate):
        arr = np.asarray(candidate, dtype=float)
        if arr.ndim == 2:
            return np.asarray([self.evaluate_constraints(row) for row in arr], dtype=float)
        normalized, x = _candidate(self.binding, arr)
        return np.asarray(_constraint_values(normalized, x), dtype=float)


class ProblemUniformInitializer(UniformInitializer):
    """Lab bridge: original uniform RNG plus explicit vector-bound identity.

    The framework initializer's checkpoint identity accepts scalar bounds;
    this adapter records the actual ordered variable bounds instead.
    """
    def __init__(self, binding, dimension):
        pairs = problem_bounds(binding, dimension)
        super().__init__(low=[p[0] for p in pairs], high=[p[1] for p in pairs])

    def checkpoint_identity(self):
        return {"schema": "nsgablack.lab.problem_uniform/v1", "bounds":
                [[float(low), float(high)] for low, high in zip(self.low, self.high)]}


def build_problem(settings):
    return LabProblem(settings["dimension"], settings["problem"])


def problem_definition_source():
    """Copy the exact checked interpreter, never splice an expression into code."""
    return Path(__file__).read_text(encoding="utf-8")


def problem_definition_contract():
    """One JSON-native contract for manual editing and AI prompt construction."""
    return dict(component="problem.expression", example=dict(component="problem.expression", parameters=dict(
        variables=[dict(name="x", low=0., high=10., type="continuous")],
        objectives=[dict(name="利润", expression="8*x-x**2", direction="max")],
        constraints=[dict(name="资源", expression="x-6", relation="<=", rhs=0., tolerance=0.)])),
        variables=dict(count="1..8", required=["name", "low", "high"], type="continuous only",
                       name="ASCII letter followed by letters/digits/underscore, 1..32; no function/constant names",
                       bounds="finite -1000000..1000000, low < high"),
        objectives=dict(count="1..2", required=["name", "expression", "direction"], direction=["min", "max"],
                        semantics="Write the user formula unchanged; max is negated only at algorithm evaluation and restored for display."),
        constraints=dict(count="0..8", required=["name", "expression", "relation", "rhs"],
                         relation=["<=", ">=", "=="], rhs="finite numeric constant",
                         tolerance="nonnegative absolute tolerance, default 0; complex RHS can be moved into expression"),
        formulas=dict(variables="declared names only", constants=list(_CONSTANTS), functions=list(_FUNCTIONS),
                      operations=["+", "-", "*", "/", "%", "** integer literal -12..12"],
                      limit="512 characters, 128 AST nodes, 24 nested levels; finite results <=1e100",
                      forbidden=["Python code", "imports", "attributes", "indexing", "lists", "comparisons", "arbitrary calls"]),
        dimension="must equal variables length; derive when omitted; update it with edited variables",
        initializer=dict(component="repr.problem_uniform", parameters={}, semantics="sample each variable within its actual Problem bounds"),
        repair="clip/projection use the same per-variable Problem bounds; arbitrary nonlinear constraints are evaluated, not automatically solved",
        missing_information="Ask for missing variable bounds/objective formulas or direction; never invent an external evaluator or integer support.")


__all__ = ["normalize_problem", "problem_bounds", "objective_count", "objective_definitions", "evaluate_problem",
           "display_objectives", "LabProblem", "ProblemUniformInitializer", "build_problem",
           "problem_definition_source", "problem_definition_contract"]
