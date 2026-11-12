"""Closed, editable assembly documents compiled to the formal Case scaffold.

This is a bounded compiler to SearchPlan/PoolTask, not a second algorithm loop.
Catalog discovery, normalization and source preview never construct an Adapter.
Limits below are private Lab trial limits, not limits of the framework APIs.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
import math
import re
from textwrap import dedent

from .lab_problem import (normalize_problem, objective_count, problem_bounds,
                          problem_definition_contract, problem_definition_source)

ASSEMBLY_SCHEMA = "nsgablack.lab.assembly/v1"


def _int(default, low, high, label):
    return dict(type="int", default=default, min=low, max=high, label=label)


def _float(default, low, high, label):
    return dict(type="float", default=default, min=low, max=high, label=label)


def _choice(default, choices, label):
    return dict(type="str", default=default, choices=choices, label=label)


_COMMON = {
    "seed": _int(17, 0, 2147483647, "随机种子"),
    "dimension": _int(2, 1, 8, "候选维度（等于问题变量数）"),
    "initial_count": _int(12, 1, 64, "母池初始解数"),
    "max_steps": _int(20, 1, 50, "逻辑提交预算"),
}
_POP = _int(6, 4, 24, "种群大小")
_BATCH = _int(2, 1, 24, "每步候选数")
_AGG = _choice("sum", ["sum", "first"], "本算法比较规则；不改原始目标")


def _component(key, label, parameters=None, *, catalog_key=None, source="framework", **extra):
    params = parameters or {}
    return dict(key=key, label=label, catalog_key=catalog_key, source=source,
                parameters=params, defaults={k: v["default"] for k, v in params.items()}, **extra)


_ADAPTERS = [
    _component("adapter.nsga2", "GA / NSGA-II", {
        "population_size": _POP, "offspring_size": _int(6, 1, 24, "每代后代数"),
        "crossover_rate": _float(.9, 0., 1., "交叉率")}, catalog_key="adapter.nsga2",
        constructor="NSGA2Adapter", config="NSGA2Config", objectives=[1, 2],
        changes=["native", "ga_mask", "ga_blend"], pool_modes=["initialize", "compete"],
        operations={"initializer": "initialize", "mutator": "mutate", "parent_selector": "select",
                    "selector": "select", "repair": "repair", "change": "change", "pool_maintenance": "maintain"},
        publishes_views=True, unit="PopulationUnit", restart=False),
    _component("adapter.moead", "MOEA/D", {"population_size": _POP, "batch_size": _BATCH,
        "neighborhood_size": _int(4, 2, 24, "方向邻域大小"),
        "decomposition": _choice("weighted_sum", ["weighted_sum", "tchebycheff"], "方向比较"),
        "variation": _choice("de", ["de", "pipeline"], "原生变化方式")}, catalog_key="adapter.moead",
        constructor="MOEADAdapter", config="MOEADConfig", objectives=[2],
        changes=["native", "moead_blend"], pool_modes=["initialize", "compete"],
        operations={"initializer": "initialize", "mutator": "mutate", "change": "change", "selector": "select",
                    "repair": "repair", "pool_maintenance": "maintain"},
        publishes_views=True, unit="DecompositionUnit", restart=False),
    _component("adapter.vns", "VNS", {"batch_size": _int(1, 1, 8, "邻域批次"),
        "k_max": _int(3, 1, 8, "邻域上限"), "base_sigma": _float(.15, .001, 2., "基础邻域尺度"),
        "scale": _float(1.7, 1., 3., "邻域尺度倍数"), "max_sigma": _float(.7, .01, 4., "最大邻域尺度"),
        "restart_on_stagnation": dict(type="bool", default=False, label="停滞后随机重启"),
        "objective_aggregation": _AGG}, catalog_key="adapter.vns", constructor="VNSAdapter", config="VNSConfig",
        objectives=[1, 2], changes=["native", "gaussian"], pool_modes=["initialize", "refine"],
        operations={"initializer": "initialize", "mutator": "mutate", "selector": "select",
                    "change": "change", "pool_maintenance": "maintain"},
        publishes_views=False, unit="CandidateUnit + NeighborhoodUnit", restart=True),
    _component("adapter.sa", "模拟退火 SA", {"batch_size": _int(1, 1, 8, "邻域批次"),
        "initial_temperature": _float(2., .001, 100., "起始温度"),
        "cooling_rate": _float(.95, .01, 1., "降温率"),
        "base_sigma": _float(.15, .001, 2., "基础扰动尺度"), "objective_aggregation": _AGG},
        catalog_key="adapter.sa", constructor="SimulatedAnnealingAdapter", config="SAConfig", objectives=[1, 2],
        changes=["native"], pool_modes=["initialize", "refine"],
        operations={"initializer": "initialize", "mutator": "mutate", "selector": "select", "repair": "repair"},
        publishes_views=False, unit="TrajectoryUnit", restart=True),
    _component("adapter.de", "差分进化 DE", {"population_size": _POP, "batch_size": _BATCH,
        "differential_weight": _float(.7, .01, 2., "差分权重"),
        "crossover_rate": _float(.9, 0., 1., "交叉率"),
        "strategy": _choice("rand1bin", ["rand1bin", "best1bin"], "差分策略"),
        "objective_aggregation": _AGG}, catalog_key="adapter.de", constructor="DifferentialEvolutionAdapter",
        config="DEConfig", objectives=[1, 2], changes=["native"], pool_modes=["initialize"],
        operations={"initializer": "initialize", "mutator": "mutate", "selector": "select", "repair": "repair"},
        publishes_views=True, unit="DifferentialPopulationUnit", restart=False),
    _component("adapter.pattern_search", "坐标模式搜索", {
        "max_directions": _int(2, 1, 8, "考察坐标数"),
        "step_size": _float(.2, .001, 2., "初始步长"),
        "expansion": _float(1.2, 1., 3., "成功扩张倍数"),
        "contraction": _float(.6, .01, .99, "失败收缩倍数"), "objective_aggregation": _AGG},
        catalog_key="adapter.pattern_search", constructor="PatternSearchAdapter", config="PatternSearchConfig",
        objectives=[1, 2], changes=["native"], pool_modes=["initialize", "refine"],
        operations={"initializer": "initialize", "selector": "select", "repair": "repair"},
        publishes_views=False, unit="PollUnit", restart=True),
]
_COMPONENTS = {
    "adapters": _ADAPTERS,
    "problems": [
        _component("problem.two_centers", "双中心距离（原始双目标）", source="lab", objectives=2),
        _component("problem.sphere", "Sphere（原始单目标）", source="lab", objectives=1),
        _component("problem.expression", "自定义变量、目标与约束公式", source="lab", objectives=[1, 2],
                   definition=problem_definition_contract()),
    ],
    "initializers": [_component("repr.problem_uniform", "按问题逐变量边界生成初值", source="lab",
                               constructor="ProblemUniformInitializer"),
                    _component("repr.uniform", "预设问题的均匀随机初值", {
        "low": _float(-2., -2., 2., "下界"), "high": _float(2., -2., 2., "上界")},
        source="framework", constructor="UniformInitializer")],
    "mutators": [
        _component("repr.gaussian_mutation", "固定高斯变化", {"sigma": _float(.12, .001, 2., "标准差")},
            catalog_key="repr.gaussian_mutation", constructor="GaussianMutation"),
        _component("repr.context_gaussian", "跟随算法上下文的高斯变化", {
            "base_sigma": _float(.12, .001, 2., "无算法尺度时的标准差")},
            catalog_key="repr.context_gaussian", constructor="ContextGaussianMutation"),
    ],
    "repairs": [
        _component("repr.clip", "截断到问题的逐变量边界", constructor="ClipRepair"),
        _component("repr.box_projection", "投影到问题的逐变量边界", constructor="ProjectionRepair"),
    ],
    "biases": [_component("bias.l2_preference", "偏好较小的候选范数（软评分）", {
        "weight": _float(.1, 0., 2., "软偏好权重")}, catalog_key="bias.callable", source="lab",
        notes="用正式 CallableBias 包装具名 L2 规则；只影响选择视图，raw 不改写。")],
    "plugins": [_component("plugin.pareto_archive", "Pareto 档案", {
        "max_size": _int(32, 1, 128, "每段最多保留数"),
        "update_every": _int(1, 1, 10, "提交代更新间隔")}, catalog_key="plugin.pareto_archive")],
}
_BY_GROUP = {group: {row["key"]: row for row in rows} for group, rows in _COMPONENTS.items()}
_ID = re.compile(r"[a-z][a-z0-9_]{0,23}\Z")


def assembly_catalog() -> dict:
    """Bounded supported bindings, preserving real Catalog identities separately."""
    return deepcopy(dict(schema=ASSEMBLY_SCHEMA, common_parameters=_COMMON, components=_COMPONENTS,
        problem_definition=problem_definition_contract(),
        limits=dict(nodes=6, plan_depth=5, expanded_stages=128, children=6,
                    purpose="实验台 CPU 小预算试跑限额，不是框架算法/API 限额"),
        plan_kinds=["stage", "serial", "multi", "repeat"],
        document_shape=dict(
            required=["nodes"],
            optional=["schema", "recipe", *_COMMON, "problem", "pipeline", "bias", "plugins", "plan"],
            binding={"component": "supported component key", "parameters": "only declared parameters"},
            node={"id": "unique [a-z][a-z0-9_]{0,23}", "component": "adapters key",
                  "parameters": "component parameter object", "change": "one of component.changes",
                  "input": {"mode": ["initialize", "refine"],
                            "source": ["main", {"adapter": "another node id", "views": ["all", "random"],
                                                 "view_count": "positive integer only for random"}],
                            "count": "positive integer or all; initialize exactly population size or 1",
                            "steps": "1..8 accepted local updates including baseline", "shuffle": "boolean"},
                  "return_from": "null or refining node id; population compete interface required"},
            plan={"stage": {"kind": "stage", "node": "declared node id", "label": "optional unique identifier",
                            "action": ["search", "compete"],
                            "steps": "1..20 for search; null for refinement/compete"},
                  "serial": {"kind": "serial", "children": "1..6 plan objects"},
                  "multi": {"kind": "multi", "children": "1..6 disjoint-owner plan objects"},
                  "repeat": {"kind": "repeat", "times": "1..10", "body": "one plan object"}},
            rules=["Unknown fields, implicit coercion, arbitrary Python/import/path are rejected.",
                   "Source views require an earlier publishing stage; parallel siblings cannot bootstrap one another.",
                   "The same node id may recur serially, never in concurrent branches; construct it once.",
                   "Refinement/compete stages wait for their PoolTask; budget lives at input.steps, not stage.steps.",
                   "A compete stage requires prior population search and a completed return_from refinement.",
                   "A final-result request is returned once; repeat requires a fresh refinement in each iteration.",
                   "A directly main-seeded refiner does not publish derived views; nested views require a view source.",
                   "max_steps is a global committed budget; an incomplete plan is reported explicitly."]),
        unsupported=[
            dict(component="adapter.bayesian_optimization", reason="BO 需要模型/观测与求值证据绑定；当前不接受通用 Pool initialize，不能当成一个软 Bias。"),
            dict(component="adapter.cmaes", reason="CMA-ES 的整批更新与修复/部分接纳契约需要专用装配，未开放此通用池绑定。"),
            dict(component="adapter.map_elites", reason="MAP-Elites 需要描述符、cell 与 archive 关系绑定，尚未开放该编辑器。"),
        ],
        notes=["自由选择支持的组件与组合；不是任意 Python/module 执行入口。",
               "Unit 使用算法的原生默认 binding，读取/预览不创建 Unit。",
               "精修显式绑定源视图；返回竞争显式绑定本请求最终结果。",
               "parallel 是共享正式 Router 的多分支提案，不保证 CPU 同时执行。",
               "参数未全量开放；目录只列本版已验证绑定。支持面之外请导出后扩展。"] ))


def _object(value, allowed, label):
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} 必须是对象")
    if any(not isinstance(k, str) for k in value):
        raise ValueError(f"{label} 的键必须是字符串")
    extra = set(value).difference(allowed)
    if extra:
        raise ValueError(f"{label} 不支持字段：{', '.join(sorted(extra))}")
    return dict(value)


def _parameter(value, rule, label):
    typ = rule["type"]
    valid = ((typ == "int" and type(value) is int)
             or (typ == "float" and type(value) in (int, float) and math.isfinite(value))
             or (typ == "bool" and type(value) is bool)
             or (typ == "str" and isinstance(value, str)))
    if not valid or ("min" in rule and not rule["min"] <= value <= rule["max"]):
        raise ValueError(f"{label} 类型或范围不正确；试跑范围 {rule.get('min')}..{rule.get('max')}")
    if "choices" in rule and value not in rule["choices"]:
        raise ValueError(f"{label} 只支持 {rule['choices']}")
    return float(value) if typ == "float" else value


def _binding(value, group):
    raw = _object(value, {"component", "parameters"}, group)
    key = raw.get("component")
    if not isinstance(key, str) or key not in _BY_GROUP[group]:
        raise ValueError(f"{group} 不支持组件 {key!r}；请查看 assembly_catalog")
    record = _BY_GROUP[group][key]
    params = _object(raw.get("parameters", {}), record["parameters"], key)
    return dict(component=key, parameters={name: _parameter(params.get(name, rule["default"]), rule,
        f"{key}.{name}") for name, rule in record["parameters"].items()})


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label} 必须为小写字母开头的 1..24 位字母数字下划线")
    return value


def normalize_assembly(value: Mapping) -> dict:
    """Validate closed syntax, ownership, component contracts and plan causality."""
    raw = _object(value, {"schema", "recipe", *_COMMON, "problem", "pipeline", "bias", "plugins", "nodes", "plan"}, "装配")
    if raw.get("schema", ASSEMBLY_SCHEMA) != ASSEMBLY_SCHEMA or raw.get("recipe", "assembly") != "assembly":
        raise ValueError("不支持的自由装配 schema/recipe")
    declared_problem = raw.get("problem", {"component": "problem.two_centers"})
    checked_problem = normalize_problem(declared_problem)
    if "dimension" not in raw and checked_problem["component"] == "problem.expression":
        raw["dimension"] = len(checked_problem["parameters"]["variables"])
    result = dict(schema=ASSEMBLY_SCHEMA, recipe="assembly", **{k: _parameter(raw.get(k, r["default"]), r, k)
                  for k, r in _COMMON.items()})
    result["problem"] = normalize_problem(checked_problem, result["dimension"])
    pipeline = _object(raw.get("pipeline", {}), {"initializer", "mutator", "repair"}, "pipeline")
    result["pipeline"] = {
        "initializer": _binding(pipeline.get("initializer", {"component": "repr.uniform"}), "initializers"),
        "mutator": (None if pipeline.get("mutator", {}) is None else _binding(
            pipeline.get("mutator", {"component": "repr.context_gaussian"}), "mutators")),
        "repair": _binding(pipeline.get("repair", {"component": "repr.clip"}), "repairs"),
    }
    initializer = result["pipeline"]["initializer"]
    if initializer["component"] == "repr.uniform":
        bounds = initializer["parameters"]
        if bounds["low"] >= bounds["high"]:
            raise ValueError("初值下界必须严格小于上界")
        if result["problem"]["component"] == "problem.expression":
            if bounds != {"low": -2., "high": 2.}:
                raise ValueError("自定义问题初值须用 repr.problem_uniform；请在变量定义中设置各自边界")
            result["pipeline"]["initializer"] = _binding({"component": "repr.problem_uniform"}, "initializers")
    result["bias"] = None if raw.get("bias") is None else _binding(raw["bias"], "biases")
    plugins = raw.get("plugins", [])
    if not isinstance(plugins, list) or len(plugins) > 1:
        raise ValueError("本版最多选择一个 Pareto 档案插件")
    result["plugins"] = [_binding(item, "plugins") for item in plugins]
    nodes = raw.get("nodes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 6:
        raise ValueError("自由装配需要 1..6 个算法实例")
    normalized_nodes = []
    objectives = objective_count(result["problem"])
    for item in nodes:
        node = _object(item, {"id", "component", "parameters", "change", "input", "return_from"}, "算法实例")
        binding = _binding({k: v for k, v in node.items() if k in {"component", "parameters"}}, "adapters")
        meta = _BY_GROUP["adapters"][binding["component"]]
        ident = _identifier(node.get("id"), "算法 id")
        if objectives not in meta["objectives"]:
            raise ValueError(f"{ident}: {meta['label']} 在实验台不支持该问题的 {objectives} 个原始目标")
        change = node.get("change", "native")
        if change not in meta["changes"]:
            raise ValueError(f"{ident}: 不支持变化绑定 {change!r}，支持 {meta['changes']}")
        params = binding["parameters"]
        size = params.get("population_size", 1)
        if binding["component"] == "adapter.moead" and params["neighborhood_size"] > size:
            raise ValueError(f"{ident}: 方向邻域不能大于种群")
        if params.get("batch_size", 1) > size and "population_size" in params:
            raise ValueError(f"{ident}: batch_size 不能大于种群")
        inp = _object(node.get("input", {}), {"mode", "source", "count", "steps", "shuffle"}, ident + ".input")
        mode = inp.get("mode", "initialize")
        if mode not in {"initialize", "refine"} or mode not in meta["pool_modes"]:
            raise ValueError(f"{ident}: 不支持 Pool 输入模式 {mode!r}")
        source = inp.get("source", "main")
        if source != "main":
            source = _object(source, {"adapter", "views", "view_count"}, ident + ".source")
            creator = _identifier(source.get("adapter"), "来源算法 id")
            views = source.get("views", "all")
            if views not in {"all", "random"}:
                raise ValueError("视图选择只支持 all 或 random")
            if views == "all" and "view_count" in source:
                raise ValueError("all 视图不接受 view_count；请用 random")
            source = dict(adapter=creator, views=views)
            if views == "random":
                source["view_count"] = _parameter(inp["source"].get("view_count", 1), _int(1, 1, 24, "视图数"), "view_count")
            if mode != "refine":
                raise ValueError("按创建者选视图只用于精修；初始化本版使用母池")
        count = inp.get("count", size if mode == "initialize" else "all")
        if count != "all":
            count = _parameter(count, _int(1, 1, 64, "取解数"), ident + ".count")
        if mode == "initialize" and count != size:
            raise ValueError(f"{ident}: 初值数须为其算法需要的 {size}，不隐含补齐或丢弃")
        if mode == "initialize" and size > result["initial_count"]:
            raise ValueError(f"{ident}: 母池初值少于所需成员数")
        steps = _parameter(inp.get("steps", 2), _int(2, 1, 8, "精修步数"), ident + ".steps")
        shuffle = _parameter(inp.get("shuffle", False), dict(type="bool"), ident + ".shuffle")
        if mode == "refine" and binding["component"] == "adapter.vns" and params["restart_on_stagnation"]:
            raise ValueError("池精修 VNS 不启用随机重启；起点由冻结池任务指定")
        if change == "native" and result["pipeline"]["mutator"] is None and (
            "mutator" in meta["operations"] and binding["component"] != "adapter.moead"
            or binding["component"] == "adapter.moead" and params["variation"] == "pipeline"):
            raise ValueError(f"{ident}: 原生变化需要装配 mutator，不能静默不移动")
        ret = node.get("return_from")
        if ret is not None:
            ret = _identifier(ret, "返回结果来源")
            if "compete" not in meta["pool_modes"]:
                raise ValueError(f"{ident}: 没有 Pool compete 接口，不能接受返回竞争")
        normalized_nodes.append(dict(id=ident, **binding, change=change,
            input=dict(mode=mode, source=source, count=count, steps=steps, shuffle=shuffle), return_from=ret))
    by_id = {node["id"]: node for node in normalized_nodes}
    if len(by_id) != len(normalized_nodes):
        raise ValueError("算法实例 id 必须唯一；同类型算法用不同 id")
    for node in normalized_nodes:
        source = node["input"]["source"]
        if isinstance(source, dict):
            if source["adapter"] not in by_id or source["adapter"] == node["id"]:
                raise ValueError("精修必须引用另一个已声明实例")
            producer = by_id[source["adapter"]]
            meta = _BY_GROUP["adapters"][producer["component"]]
            if not meta["publishes_views"] and producer["input"]["mode"] != "refine":
                raise ValueError("源算法没有原生公开视图，且未装配发布结果的精修任务")
            if (not meta["publishes_views"] and producer["input"]["source"] == "main"):
                raise ValueError("从母池直接精修不发布派生视图；嵌套精修须继承明确的来源视图")
            if source["views"] == "random":
                max_views = producer["parameters"].get("population_size", result["initial_count"]) if producer["component"] == "adapter.moead" else 1
                # A refining source may publish one view per selected parent; runtime freezes the exact set.
                if producer["input"]["mode"] != "refine" and source["view_count"] > max_views:
                    raise ValueError("随机视图数大于来源实例可以发布的视图数")
        ret = node["return_from"]
        if ret is not None and (ret not in by_id or by_id[ret]["input"]["mode"] != "refine"):
            raise ValueError("返回竞争只消费已声明精修实例的当前请求最终结果")
    counter = [0]
    labels = set()
    reserved_labels = set()

    def reserve_labels(p, depth=0):
        if depth > 6 or not isinstance(p, Mapping):
            return
        if isinstance(p.get("label"), str):
            reserved_labels.add(p["label"])
        if isinstance(p.get("children"), list):
            for child in p["children"][:6]:
                reserve_labels(child, depth + 1)
        reserve_labels(p.get("body"), depth + 1)

    reserve_labels(raw.get("plan"))

    def plan(value, depth=0):
        if depth > 5:
            raise ValueError("试跑计划最多嵌套 5 层")
        p = _object(value, {"kind", "node", "label", "steps", "action", "children", "times", "body"}, "plan")
        kind = p.get("kind")
        if kind == "stage":
            p = _object(p, {"kind", "node", "label", "steps", "action"}, "stage")
            owner = p.get("node")
            if not isinstance(owner, str) or owner not in by_id:
                raise ValueError("stage 引用了未声明的算法实例")
            counter[0] += 1
            auto_label = f"stage_{counter[0]}"
            while "label" not in p and (auto_label in labels or auto_label in reserved_labels):
                counter[0] += 1
                auto_label = f"stage_{counter[0]}"
            label = _identifier(p.get("label", auto_label), "阶段 label")
            if label in labels:
                raise ValueError("阶段 label 必须唯一；重复执行请用 repeat")
            labels.add(label)
            action = p.get("action", "search")
            if action not in {"search", "compete"}:
                raise ValueError("stage.action 只支持 search 或 compete")
            is_task = action == "compete" or by_id[owner]["input"]["mode"] == "refine"
            steps = p.get("steps", None if is_task else 3)
            if is_task and steps is not None:
                raise ValueError("精修/返回竞争等待 PoolTask 完成，不接受 stage.steps；请设置 input.steps")
            if not is_task:
                steps = _parameter(steps, _int(3, 1, 20, "阶段步数"), label + ".steps")
            if action == "compete" and by_id[owner]["return_from"] is None:
                raise ValueError("compete 阶段须明确 node.return_from")
            return dict(kind=kind, node=owner, label=label, steps=steps, action=action)
        if kind in {"serial", "multi"}:
            _object(p, {"kind", "children"}, kind)
            children = p.get("children")
            if not isinstance(children, list) or not 1 <= len(children) <= 6:
                raise ValueError("serial/multi 需要 1..6 个孩子")
            return dict(kind=kind, children=[plan(c, depth + 1) for c in children])
        if kind == "repeat":
            _object(p, {"kind", "times", "body"}, kind)
            times = _parameter(p.get("times"), _int(2, 1, 10, "重复次数"), "repeat.times")
            return dict(kind=kind, times=times, body=plan(p.get("body"), depth + 1))
        raise ValueError("plan.kind 只支持 stage、serial、multi、repeat")

    result["nodes"] = normalized_nodes
    result["plan"] = plan(raw.get("plan", dict(kind="stage", node=normalized_nodes[0]["id"])))
    used, expanded = set(), [0]

    def owners(p):
        if p["kind"] == "stage":
            return {p["node"]}
        return set().union(*(owners(c) for c in ([p["body"]] if p["kind"] == "repeat" else p["children"])))

    def causal(p, available, completed):
        kind = p["kind"]
        if kind == "stage":
            expanded[0] += 1
            if expanded[0] > 128:
                raise ValueError("试跑计划展开超过 128 个阶段")
            node = by_id[p["node"]]
            used.add(node["id"])
            source = node["input"]["source"]
            if p["action"] == "search" and isinstance(source, dict) and source["adapter"] not in available:
                raise ValueError(f"{p['label']}: 来源视图尚未发布；不能读取并行兄弟或后续阶段")
            if p["action"] == "compete":
                if node["id"] not in available or node["return_from"] not in completed:
                    raise ValueError("返回竞争之前必须先运行所属种群，并等待本轮新精修完成；禁止重复归还旧请求")
                completed = completed - {node["return_from"]}
            # Search/competition changes the source population: old refinements
            # of that view cannot silently be treated as this new handoff.
            stale = {node["id"]}
            while True:
                affected = {n["id"] for n in normalized_nodes if isinstance(n["input"]["source"], dict)
                            and n["input"]["source"]["adapter"] in stale}
                if affected <= stale:
                    break
                stale |= affected
            completed = completed - stale
            return available | {node["id"]}, completed | ({node["id"]} if node["input"]["mode"] == "refine" else set())
        if kind == "serial":
            for child in p["children"]:
                available, completed = causal(child, available, completed)
            return available, completed
        if kind == "repeat":
            for _ in range(p["times"]):
                available, completed = causal(p["body"], available, completed - owners(p["body"]))
            return available, completed
        occupied, outcomes = set(), []
        branches = [owners(child) for child in p["children"]]
        for names in branches:
            others = set().union(*(branch for branch in branches if branch is not names))
            for name in names:
                node = by_id[name]
                source = node["input"]["source"]
                if ((isinstance(source, dict) and source["adapter"] in others)
                        or node["return_from"] in others):
                    raise ValueError("来源视图尚未发布为本分支的稳定输入：并行分支不能依赖另一分支的变化视图或结果；先加串行屏障")
        for child in p["children"]:
            names = owners(child)
            if names & occupied:
                raise ValueError("同一可变算法实例不能出现在并行的两条分支中")
            occupied |= names
            outcomes.append(causal(child, set(available), set(completed)))
        invalidated = set().union(*(completed - outcome[1] for outcome in outcomes))
        return set().union(available, *(o[0] for o in outcomes)), set().union(*(o[1] for o in outcomes)) - invalidated

    causal(result["plan"], set(), set())
    if used != set(by_id):
        raise ValueError("每个声明的算法实例都必须出现在计划中；不会保留假挂组件")
    for node in normalized_nodes:
        if node["return_from"] and not any(p["node"] == node["id"] and p["action"] == "compete" for p in _leaves(result["plan"])):
            raise ValueError("声明 return_from 后须安排对应 compete 阶段")
    return result


def _leaves(plan):
    if plan["kind"] == "stage":
        yield plan
    else:
        for child in ([plan["body"]] if plan["kind"] == "repeat" else plan["children"]):
            yield from _leaves(child)


def assembly_from_recipe(recipe_id: str) -> dict:
    """Recipes are editable starting documents, never a combination allowlist."""
    key = {"ga": "adapter.nsga2", "vns": "adapter.vns", "moead": "adapter.moead"}
    if recipe_id not in {*key, "ga_vns"}:
        raise ValueError("未知装配起点")
    if recipe_id == "ga_vns":
        return normalize_assembly(dict(nodes=[
            dict(id="ga", component=key["ga"], change="ga_mask", return_from="vns"),
            dict(id="vns", component=key["vns"], change="gaussian", input=dict(mode="refine",
                 source=dict(adapter="ga", views="all"), count="all", steps=2))],
            plan=dict(kind="serial", children=[dict(kind="stage", node="ga", steps=2),
                 dict(kind="stage", node="vns"), dict(kind="stage", node="ga", action="compete")]), max_steps=20))
    return normalize_assembly(dict(nodes=[dict(id=recipe_id, component=key[recipe_id])],
        plan=dict(kind="stage", node=recipe_id, steps=8), max_steps=8))


def _source(value):
    return dedent(value).lstrip("\n").rstrip() + "\n"


def _adapter_source(spec):
    lines = [
        '"""原生算法只创建一次；既有 SearchPlan / Router / PoolTask 执行计划。"""',
        "from nsgablack import adapters as A",
        "from nsgablack.adapters.search_plan import SearchPlanAdapter, stage, serial, multi, repeat",
        "from .changes import ga_change, ga_blend, vns_change, moead_change", "",
    ]
    leaves = tuple(_leaves(spec["plan"]))
    for node in spec["nodes"]:
        if node["return_from"]:
            lines += [f"def return_results_{node['id']}(control, context):", "    del context",
                      f"    return control.adapter.get_pool_task_results(control, {node['return_from']!r})", ""]
    lines += ["def build_adapter(settings):", "    nodes = {}",
              "    settings_by_id = {node['id']: node for node in settings['nodes']}"]
    changes = dict(ga_mask="ga_change", ga_blend="ga_blend", gaussian="vns_change", moead_blend="moead_change")
    for node in spec["nodes"]:
        meta = _BY_GROUP["adapters"][node["component"]]
        params = [f"**settings_by_id[{node['id']!r}]['parameters']"]
        if node["component"] in {"adapter.sa", "adapter.moead"}:
            params += ["random_seed=settings['seed']"]
        if node["change"] != "native":
            params += ["change=" + changes[node["change"]]]
        lines += [f"    nodes[{node['id']!r}] = A.{meta['constructor']}(name={node['id']!r}, {', '.join(params)})"]
    lines += ["    strategies = []"]
    for node in spec["nodes"]:
        name, inp = node["id"], node["input"]
        searches = tuple(p["label"] for p in leaves if p["node"] == name and p["action"] == "search")
        competes = tuple(p["label"] for p in leaves if p["node"] == name and p["action"] == "compete")
        source = inp["source"]
        selection = "None" if source == "main" else (
            f"A.subpools.all(nodes[{source['adapter']!r}])" if source["views"] == "all" else
            f"A.subpools.random({source['view_count']}, nodes[{source['adapter']!r}])")
        task = f"A.PoolTaskSpec(select={selection}, mode={inp['mode']!r}, count={inp['count']!r}, steps={inp['steps']}, shuffle={inp['shuffle']!r}, phases={searches!r})"
        lines += [f"    owned = nodes[{name!r}]"]
        if competes:
            lines += [f"    owned = A.PoolTaskAdapter(owned, {task}, role={name + '_seed'!r}, namespace='lab')"]
            task = f"A.PoolTaskSpec(return_results_{name}, mode='compete', count='all', shuffle=False, phases={competes!r})"
        lines += [f"    strategies.append(A.StrategySpec(name={name!r}, adapter=owned, pool_task={task}))"]

    def expression(p):
        kind = p["kind"]
        if kind == "stage":
            return f"stage({p['node']!r}, steps={p['steps']!r}, label={p['label']!r})"
        if kind == "repeat":
            return f"repeat(times={p['times']}, body={expression(p['body'])})"
        return kind + "(" + ", ".join(expression(c) for c in p["children"]) + ")"
    capacity = sum(max(n["parameters"].get("population_size", 1), n["parameters"].get("batch_size", 1)) for n in spec["nodes"])
    lines += [f"    plan = {expression(spec['plan'])}",
              f"    return SearchPlanAdapter(plan, strategies, name='lab_assembly', config=A.MultiStrategyConfig(total_batch_size={capacity}, adapt_weights=False))", ""]
    return "\n".join(lines)


def assembly_overlay(value: Mapping) -> dict[str, str]:
    """Compile checked data to editable ordinary formal Project source files."""
    from .lab_project import _PROJECT_CONFIG, _CHANGE, _PLUGINS
    spec = normalize_assembly(value)
    pipeline = spec["pipeline"]
    ini = _BY_GROUP["initializers"][pipeline["initializer"]["component"]]["constructor"]
    init_args = ("settings['problem'], settings['dimension']" if ini == "ProblemUniformInitializer" else
                 "**settings['pipeline']['initializer']['parameters']")
    mut = pipeline["mutator"]
    mutate = "None" if mut is None else _BY_GROUP["mutators"][mut["component"]]["constructor"] + "(**settings['pipeline']['mutator']['parameters'])"
    repair = _BY_GROUP["repairs"][pipeline["repair"]["component"]]["constructor"] + "(low=low, high=high)"
    pipeline_source = _source(f'''
        """共享问题候选管线，Adapter 从此获取真实算子。"""
        from nsgablack.representation import (RepresentationPipeline, UniformInitializer,
            GaussianMutation, ContextGaussianMutation, ClipRepair, ProjectionRepair)
        from ..problem import ProblemUniformInitializer, problem_bounds


        def build_pipeline(settings, *, resource_context=None, component_overrides=None):
            del resource_context, component_overrides
            pairs = problem_bounds(settings['problem'], settings['dimension'])
            low, high = [p[0] for p in pairs], [p[1] for p in pairs]
            return RepresentationPipeline(initializer={ini}({init_args}), mutator={mutate}, repair={repair})
    ''')
    bias_source = _source('''
        """固定具名软偏好；raw Problem 反馈始终保留。"""
        import numpy as np
        from nsgablack.bias import BiasModule
        from nsgablack.bias.domain.callable_bias import CallableBias


        def squared_norm(candidate):
            return float(np.sum(np.asarray(candidate, dtype=float) ** 2))


        def build_bias(settings):
            module = BiasModule()
            binding = settings["bias"]
            if binding is not None:
                module.add(CallableBias("lab_l2_preference", squared_norm),
                           weight=binding["parameters"]["weight"])
            return module
    ''')
    build = _source('''
        """唯一实际装配入口；预览、导出、运行共享同一份源码。"""
        from pathlib import Path
        from nsgablack.core import ComposableSolver
        from nsgablack.project import apply_solver_component_overrides
        from nsgablack.plugins import ParetoArchivePlugin, ParetoArchiveConfig
        from .adapter import build_adapter
        from .bias import build_bias
        from .config import SPEC
        from .pipeline import build_pipeline
        from .plugins import PipelineSource, LabReport
        from .problem import build_problem


        def build_solver(config=None, *, resource_context=None, component_overrides=None):
            settings = {**SPEC, **dict(config or {})}
            solver = ComposableSolver(problem=build_problem(settings),
                representation_pipeline=build_pipeline(settings), adapter=build_adapter(settings),
                bias_module=build_bias(settings), resource_context=resource_context,
                plugin_strict=True, snapshot_strict=True)
            solver.set_random_seed(settings["seed"])
            solver.set_max_steps(settings["max_steps"])
            solver.add_plugin(PipelineSource(settings["initial_count"]))
            for binding in settings["plugins"]:
                solver.add_plugin(ParetoArchivePlugin(config=ParetoArchiveConfig(**binding["parameters"])))
            solver.add_plugin(LabReport(settings, Path(__file__).resolve().parents[2] / "results"))
            apply_solver_component_overrides(solver, component_overrides)
            return solver
    ''')
    changes = _CHANGE + _source('''


        def ga_blend(request, *, rng):
            """可替换的普通函数：两亲本算术重组后加小幅噪声。"""
            a, b = request.parents[:2]
            alpha = rng.random(a.shape)
            return ChangeResult(alpha * a + (1. - alpha) * b + rng.normal(0., .08, a.shape),
                                source_refs=request.source_refs[:2])
    ''')
    readme = """# 自由装配实验项目

Project → Case → Scaffold，唯一装配入口为 `cases/search/build_solver.py`。
`lab_spec.json` 是生成此源码的闭合装配文档；源码预览、ZIP 与正式试跑完全同源。

```shell
python run_project.py --check --build-check
python run_project.py
```

Project L0 发放一个 CPU 线程；不会在 Case 内另起求解器或绕过资源授权。
运行证据位于 `.blackbase/runs/<run-id>/manifest.json`；`lab_report` 是带发布收据的 Artifact。
`results/lab_report.json` 是展示副本。

## 编辑

1. `problem/__init__.py` 定义原始目标；`pipeline/main.py` 定义初值/变异/问题修复。
2. `adapter/__init__.py` 每个算法实例创建一次，以既有 SearchPlan 的 serial/multi/repeat 编排。
3. `adapter/changes.py` 是可直接编辑的普通变化函数，无需继承新 Adapter。
4. PoolTask 显式声明初始化或逐解精修；subpools 选择固定来源实例的已发布视图。
5. 返回竞争使用 `get_pool_task_results` 读取本请求最终引用，再由原种群算法竞争。
6. Unit 使用原算法默认 builder/codec，运行前不为了预览或检查创建。

`config.py` 的共同预算、算法 parameters、管线参数、Bias 与 Plugin 参数在构造时读取。
组件类型、变化函数、池来源与计划结构明确生成为普通 Python 装配代码；修改这些结构请在实验台
编辑装配并重新导出，或直接编辑相应正式源码。导出后不承诺任意源码与图形配置自动往返。

参数范围与最多六个算法是实验台试跑限额，并非框架 API 上限。
串行分支只读前序已发布视图；并行兄弟不能隐含依赖。multi 是正式 Router 的多分支提案，
不意味着在单 CPU grant 下启动多进程。精修/竞争阶段等待任务完成，普通搜索阶段以提交配额结束。
`max_steps` 可以提前终止整个计划，报告 `plan_completed` 明示是否完整完成。
不对多目标暗猜比较规则：VNS/SA/DE/模式搜索显示 sum/first，方向精修沿冻结投影。
软偏好只改变选择反馈，原始目标/约束不会被覆盖。
"""
    # The reporter observes true assembled nodes and plugins without constructing Units.
    report = _PLUGINS.replace('"initial": self.initial, "records": self.records, "units": final["units"],',
        '"initial": self.initial, "records": self.records, "units": final["units"],\n'
        '                "assembly_components": {"problem": type(solver.problem).__name__,\n'
        '                    "plugins": [type(p).__name__ for p in solver.plugin_manager.plugins]},')
    return {
        "project_config.py": _PROJECT_CONFIG,
        "lab_spec.json": json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "README.md": readme,
        "cases/search/README.md": "# search\n\n详见项目根 README.md。\n",
        "cases/search/config.py": '"""生成此 Case 的装配文档。"""\nSPEC = ' + repr(spec) + "\n",
        "cases/search/build_solver.py": build,
        "cases/search/problem/__init__.py": problem_definition_source(),
        "cases/search/pipeline/main.py": pipeline_source,
        "cases/search/pipeline/__init__.py": "from .main import build_pipeline\n",
        "cases/search/adapter/__init__.py": _adapter_source(spec),
        "cases/search/adapter/changes.py": changes,
        "cases/search/bias/__init__.py": bias_source,
        "cases/search/plugins/__init__.py": report,
    }


__all__ = ["ASSEMBLY_SCHEMA", "assembly_catalog", "assembly_from_recipe", "normalize_assembly", "assembly_overlay"]
