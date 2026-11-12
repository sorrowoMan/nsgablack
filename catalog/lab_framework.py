"""Bounded source evidence for framework guidance, without executing components.

This is a retriever over packaged/local source, not another component registry.
Catalog descriptions remain owned by the existing TOML declarations; execution
permissions remain owned by the caller's explicit workbench assembly catalog.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re

try:
    import tomllib
except ImportError:  # Python 3.10 is still supported by the framework.
    import tomli as tomllib


SCHEMA = "nsgablack.lab_framework_context/v1"
MAX_CONTEXT_BYTES = 32768
_ROOT = Path(__file__).resolve().parent.parent
_KEY = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_EXCERPT = 1200
_MAX_FILE_BYTES = 512000
_MAX_CONTRACTS = 8
_MAX_COMPONENTS = 6

# Anchors locate current statements; neither line numbers nor summaries are
# copied here. A removed anchor becomes unavailable evidence, not a stale rule.
_CONTRACTS = (
    ("framework_roles", "Problem / Pipeline / Unit / Adapter / Bias / Plugin 的职责",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "Problem 定义问题；问题管线处理候选；", 2,
     ("框架", "职责", "架构", "framework", "pipeline", "problem")),
    ("pool_identity", "读取、派生提案与 repair 分别维护候选身份和版本",
     "docs/architecture/SOLUTION_POOL_CN.md", "`SolutionRef(pool_id, record_id, row, candidate_token)`", 9,
     ("身份", "版本", "token", "solutionref", "record_id", "同值", "相等", "repair", "引用")),
    ("pool_nested_views", "嵌套视图冻结来源、投影仅应用一次且删除不级联",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "投影池精修任务每个完成起点通过", 1,
     ("嵌套", "子池的子池", "派生视图", "后代", "父池", "父视图", "父级", "删除", "释放", "同名", "投影", "revision", "view_id", "ancestors")),
    ("pool_view_address", "按冻结 descriptor 查询历史子树，同名新视图不能接管",
     "docs/architecture/SOLUTION_POOL_CN.md", "名字参数查询当前存活视图；冻结 descriptor", 1,
     ("后代", "子树", "同名", "descriptor", "children_subpools", "寻址", "查找", "名字", "前缀")),
    ("pool_projection_once", "方向精修继承一个有效投影，只处理本层新的选择反馈",
     "docs/architecture/SOLUTION_POOL_CN.md", "每层任务直接继承一个有效 ObjectiveProjection", 1,
     ("投影", "方向", "继承", "标量", "二层", "第二层", "objectiveprojection")),
    ("cross_case_resources", "子 Case 资源在父级 L0 grant 内划分，不复制授权",
     "docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md", "父 Case 的 L0 grant 是硬上界。", 7,
     ("case", "跨case", "跨 case", "跨框架", "l0", "grant", "gpu", "授权", "资源", "resourcecontext")),
    ("cross_case_input", "跨 Case 输入必须显式传输、解释并建立本地地址",
     "docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md", "### 8.1 什么时候才需要把父池候选交给内层", 14,
     ("case", "跨case", "跨 case", "跨框架", "内层", "暖启动", "solutionref", "artifactbinding", "父池", "scope")),
    ("recovery_classification", "持久处置待核验与没有持久处置分开，恢复不重放算法",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "恢复分类由 BlackBase EvaluationEvidenceCoordinator", 1,
     ("恢复", "durable", "deferred", "abandoned", "event_ready", "重放", "证据", "围栏", "journal")),
    ("recovery_readonly", "证据检查只读，无 Problem、接纳或 Adapter 回调能力",
     "core/evidence_semantics.py", "\"\"\"Read-only optimization semantics", 5,
     ("恢复", "durable", "deferred", "abandoned", "重放", "证据", "围栏", "journal")),
    ("bo_semantics", "BO 的真实观测、模型与采集决策不能由软评分替代",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "BayesianOptimizationAdapter 将真实观测与候选成员分开。", 1,
     ("贝叶斯", "bayesian", "bo", "代理模型", "后验", "采集", "观测")),
    ("unit_inputs", "叶算子经实际 Adapter 显式捕获只读 Unit 输入",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "轨迹/区域候选关联反馈保存于 Unit.candidate_feedback", 1,
     ("unitinputspec", "unitinputs", "unit_inputs", "mutator", "步长", "sigma", "成员", "只读", "变异")),
    ("unit_member_state", "自定义成员字段随真实成员操作、草稿验证与 codec 共同维护",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "种群 Adapter 保留搜索决策，`PopulationUnit.apply_selection`", 1,
     ("member_fields", "on_members_changed", "populationchange", "步长", "年龄", "sigma", "成员", "字段")),
    ("unit_reuse", "复用默认 Unit 与扩展成员字段",
     "docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md", "## 一个用户真正需要写多少", 39,
     ("unit", "成员", "字段", "步长", "年龄", "age", "种群", "结构", "要不要")),
    ("unit_lazy", "Unit 由所属 Adapter 按实际需要创建",
     "docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md", "## Unit 的归属与按需创建", 14,
     ("unit", "创建", "初始化", "懒", "生命周期", "恢复", "暂停", "builder")),
    ("unit_members", "成员维护钩子的只读输入与扩展字段更新",
     "units/collections.py", "    def on_members_changed(self, change:", 13,
     ("成员", "字段", "步长", "年龄", "member_fields", "on_members_changed", "populationchange")),
    ("unit_member_operations", "PopulationChange 只覆盖明确的成员结构操作",
     "units/population_operations.py", "    def __post_init__(self):", 17,
     ("成员", "字段", "步长", "年龄", "sigma", "member_fields", "on_members_changed", "populationchange")),
    ("unit_member_scope", "成员局部索引不等于提案索引，repair 不冒充成员选择",
     "docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md", "部分接纳后，`PopulationChange.incoming_member_indices`", 1,
     ("成员", "步长", "sigma", "索引", "部分接纳", "repair", "on_members_changed", "populationchange")),
    ("adapter_operations", "可装配行为不等于固定四阶段循环",
     "docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md", "初始化、变化、选择、修复可以作为", 20,
     ("adapter", "算法", "交叉", "变异", "选择", "初始化", "算子", "change", "ga", "vns", "moea")),
    ("adapter_change", "完整变化函数的候选、身份与提交边界",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "VNS / MOEA-D 与 NSGA-II/III、SPEA2 提供", 12,
     ("change", "交叉", "变异", "变化", "后代", "顺序", "普通函数", "ga", "vns", "moea")),
    ("pool_context", "池存候选版本，Unit 存算法结构",
     "docs/architecture/SOLUTION_POOL_CN.md", "## 1. 解先有存放位置，再由算法使用", 18,
     ("pool", "池", "ctx", "context", "候选", "引用", "母池", "子池", "精英", "禁忌")),
    ("pool_selection", "选择与入池复用原事务",
     "docs/architecture/POOL_API_REFERENCE_CN.md", "## 0. 当前试作：选择一个 Pool", 24,
     ("精英", "pool", "池", "选择", "chosen", "inject", "淘汰", "分流")),
    ("pool_member_results", "从算法最终成员维护档案，不把 accepted 当作最终保留",
     "docs/architecture/POOL_API_REFERENCE_CN.md", "### 0.2 历史档案只收最终成员", 22,
     ("精英", "最终成员", "成员档案", "环境选择", "accepted", "request.members", "survivor")),
    ("pool_selection_commit", "精英副池与 Unit 共同提交和回滚，VNS 消费已提交集合",
     "docs/architecture/POOL_API_REFERENCE_CN.md", "### 0.3 当前可用范围", 14,
     ("精英", "最终成员", "回滚", "提交", "inject", "pool_maintenance", "survivor")),
    ("moead_projection", "方向任务冻结起点与比较投影，保留 raw 并返回当前竞争规则",
     "docs/architecture/SOLUTION_POOL_CN.md", "一次请求在开始时冻结所选方向、候选版本和投影参数。", 5,
     ("moea", "moead", "moea/d", "方向", "投影", "子问题", "scalar")),
    ("pool_refinement_scores", "投影精修直接读取方向单列，不调用普通聚合评分",
     "adapters/pool_results.py", "    def scores(self, feedback, ordinary_scores):", 17,
     ("moea", "moead", "moea/d", "方向", "投影", "子问题", "sum", "first", "poolrefinementstate")),
    ("context", "池输入通过轻量引用进入 context",
     "docs/architecture/SOLUTION_POOL_CN.md", "`pool.bind_input(refs)` 生成轻量 selection ID", 3,
     ("ctx", "context", "共享", "大对象", "矩阵", "轻量", "引用")),
    ("bias_plugin", "软评分不能改写原始求值或打开硬可行门",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "## 偏好与原始反馈", 10,
     ("bias", "偏好", "评分", "多样性", "禁忌", "可行", "约束", "贝叶斯", "bayesian")),
    ("plugin_lifecycle", "Plugin 复用 BlackBase 生命周期",
     "plugins/base.py", "class Plugin(PluginBase):", 11,
     ("plugin", "插件", "日志", "观察", "检查点", "checkpoint", "恢复", "生命周期")),
    ("plugin_participation", "Plugin 按域声明观察、建议、决定与否决",
     "docs/architecture/RUNTIME_CONTRACTS_CN.md", "ParticipationContract 按域声明 observe/advise/decide/veto", 1,
     ("plugin", "插件", "参与", "接管", "否决", "participationcontract", "veto", "decide", "observe")),
    ("framework_stack", "BlackBase / NSGABlack / MLBlack 的职责边界",
     "README.md", "## 三仓边界", 8,
     ("mlblack", "blackbase", "训练", "模型", "provider", "跨", "case", "资源", "gpu", "pinn")),
    ("repair", "问题修复与结构修复共同验收",
     "docs/architecture/JOINT_REPAIR_CN.md", "## 接口与装配", 9,
     ("repair", "修复", "可行", "约束", "半径", "部分接纳")),
    ("orchestration", "串行、并行与重复使用现有编排",
     "docs/architecture/NATURAL_SEARCH_PLANS_CN.md", "## 1. 最小写法", 32,
     ("编排", "嵌套", "串行", "并行", "repeat", "serial", "multi", "精修", "ga", "vns")),
    ("orchestration_accounting", "叶额度按非空接纳更新计数，纯切换不制造提交",
     "docs/architecture/NATURAL_SEARCH_PLANS_CN.md", "`steps` 是该位置实际收到非空接纳反馈并更新的次数。", 6,
     ("重复", "repeat", "步数", "逻辑提交", "预算", "steps", "max_steps")),
    ("orchestration_pool_tasks", "池任务每起点额度含基准，精修和竞争等待请求完成",
     "docs/architecture/NATURAL_SEARCH_PLANS_CN.md", "这里省略 stage.steps 表示等待这次池任务全部完成。", 12,
     ("重复", "repeat", "步数", "基准", "预算", "steps", "compete")),
    ("orchestration_return", "返回竞争正常消费候选，提交与失败重评仍由原事务结算",
     "docs/architecture/NATURAL_SEARCH_PLANS_CN.md", "结果提交后，GA 通过正常 compete 消费并竞争。", 2,
     ("重复", "repeat", "步数", "返回竞争", "预算", "compete")),
    ("orchestration_budget", "实验台全局预算可以提前结束计划，完成状态显式报告",
     "catalog/lab_assembly.py", "`max_steps` 可以提前终止整个计划，报告 `plan_completed`", 1,
     ("重复", "repeat", "步数", "预算", "steps", "max_steps", "plan_completed")),
)
_ENTRY_FILES = tuple(f"catalog/entries/{name}.toml" for name in (
    "adapter", "algorithm_semantics", "bias", "plugin", "representation",
    "core_architecture", "operators", "solution_pool", "unit_features", "joint_repair",
))
_ALLOWED_PATHS = frozenset(row[2] for row in _CONTRACTS) | frozenset(_ENTRY_FILES)
_CONTRACT_IDS = frozenset("contract." + row[0] for row in _CONTRACTS)
_DEFAULTS = ("framework_roles", "adapter_operations", "unit_reuse", "pool_context", "framework_stack")
_ALIASES = (
    (("ga", "遗传", "交叉"), ("nsga2", "change", "交叉", "population")),
    (("unit", "成员", "步长", "年龄", "结构"), ("unit", "population", "成员", "字段")),
    (("精英", "pool", "池", "chosen", "inject"), ("pool", "精英", "选择", "chosen", "inject")),
    (("贝叶斯", "bayesian", "bo"), ("bayesian", "bo", "采集", "观测", "预测")),
    (("cma", "协方差"), ("cma", "分布", "cohort")),
    (("map-elites", "map_elites", "格子", "质量多样性"), ("map_elites", "descriptor", "档案", "格子")),
    (("plugin", "插件", "日志", "检查点", "checkpoint"), ("plugin", "日志", "checkpoint", "生命周期")),
    (("bias", "偏好", "多样性", "禁忌"), ("bias", "preference", "diversity", "tabu")),
    (("vns", "精修", "邻域"), ("vns", "neighborhood", "精修")),
    (("moea", "方向", "子问题"), ("moead", "decomposition", "投影")),
)
_PRIORITY_CONTRACTS = {
    "pool_identity": ("身份", "版本", "token", "solutionref", "record_id", "同值", "相等"),
    "unit_members": ("成员", "字段", "步长", "年龄", "member_fields", "on_members_changed"),
    "unit_lazy": ("创建unit", "创建 unit", "懒创建", "暂停", "按需", "builder"),
    "plugin_lifecycle": ("plugin", "插件", "日志", "检查点", "checkpoint"),
    "plugin_participation": ("参与", "接管", "否决", "participationcontract", "veto", "decide", "observe"),
    "context": ("ctx", "context", "共享上下文", "大对象"),
    "bias_plugin": ("bias", "偏好", "多样性", "软评分"),
    "framework_stack": ("mlblack", "blackbase", "跨框架", "gpu", "pinn"),
    "repair": ("repair", "修复", "部分接纳"),
    "orchestration": ("编排", "嵌套", "串行", "并行", "repeat", "serial", "multi"),
}
# Reserve bounded evidence slots for the semantic boundary actually
# asked about, instead of returning only the general introduction to each topic.
# These are retrieval preferences, never copied facts or a plan-count evaluator.
_FOCUSED_CONTRACTS = (
    (("身份", "版本", "token", "solutionref", "record_id", "同值", "相等"),
     ("pool_identity",)),
    (("嵌套", "子池的子池", "派生视图", "后代", "父视图", "父级", "删除", "释放", "同名", "revision", "view_id", "ancestors"),
     ("pool_nested_views", "pool_view_address")),
    (("跨case", "跨 case", "跨框架", "内层case", "内层 case", "l0", "grant", "resourcecontext", "scope"),
     ("cross_case_resources", "cross_case_input")),
    (("恢复", "durable", "deferred", "abandoned", "event_ready", "重放", "journal", "围栏"),
     ("recovery_classification", "recovery_readonly")),
    (("贝叶斯", "bayesian", "bo", "采集", "后验", "观测"),
     ("bo_semantics",)),
    (("moea", "moead", "moea/d", "方向", "投影", "子问题", "poolrefinementstate"),
     ("moead_projection", "pool_refinement_scores", "pool_projection_once")),
    (("精英", "最终成员", "成员档案", "环境选择", "accepted", "request.members", "survivor"),
     ("pool_selection", "pool_member_results", "pool_selection_commit")),
    (("步长", "年龄", "sigma", "member_fields", "on_members_changed", "populationchange"),
     ("unit_members", "unit_member_operations", "unit_member_scope", "unit_inputs", "unit_member_state")),
    (("repeat", "步数", "多少步", "几步", "逻辑提交", "预算", "steps", "max_steps", "plan_completed", "轮次", "两轮", "每轮"),
     ("orchestration_accounting", "orchestration_pool_tasks", "orchestration_return", "orchestration_budget")),
)
_PREFERRED_COMPONENTS = (
    (("ga", "遗传", "交叉"), ("adapter.nsga2",)),
    (("unit", "成员", "字段", "步长"), ("tool.unit_binding", "tool.population_unit")),
    (("pool", "池", "chosen", "inject"), ("tool.pool",)),
    (("贝叶斯", "bayesian", "bo"), ("adapter.bayesian_optimization",)),
    (("cma", "协方差"), ("adapter.cmaes",)),
    (("map-elites", "map_elites", "格子"), ("adapter.map_elites",)),
    (("vns", "邻域", "精修"), ("adapter.vns",)),
    (("moea", "moead", "moea/d", "方向", "子问题"), ("adapter.moead",)),
)


def _contains(text: str, term: str) -> bool:
    """Do not interpret 'bo' inside unrelated English words as an algorithm."""
    if re.fullmatch(r"[a-z0-9_]+", term):
        return re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", text) is not None
    return term in text


def _query(instruction, design_notes) -> str:
    if (not isinstance(instruction, str) or len(instruction) > 8192
            or not isinstance(design_notes, str) or len(design_notes) > 8192):
        raise ValueError("framework_query_invalid")
    return (instruction + "\n" + design_notes).lower()


def _terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-z][a-z0-9_.-]{1,63}", query))
    for triggers, additions in _ALIASES:
        if any(_contains(query, term) for term in triggers):
            terms.update(additions)
    # Exact Chinese terms also retrieve existing Chinese Catalog descriptions.
    for row in _CONTRACTS:
        terms.update(term for term in row[5] if _contains(query, term))
    return terms


def _read_source(relative_path: str):
    if relative_path not in _ALLOWED_PATHS:
        raise ValueError("framework_source_forbidden")
    root = _ROOT.resolve()
    path = (root / relative_path).resolve()
    # A whitelisted symlink may not widen the source boundary.
    if not path.is_relative_to(root):
        raise ValueError("framework_source_forbidden")
    with path.open("rb") as handle:
        data = handle.read(_MAX_FILE_BYTES + 1)
    if len(data) > _MAX_FILE_BYTES:
        raise ValueError("framework_source_too_large")
    return data.decode("utf-8-sig").splitlines(), hashlib.sha256(data).hexdigest()


def _excerpt(lines, sha256, path, start, stop):
    selected = []
    length = 0
    for line in lines[start:stop]:
        added = len(line) + bool(selected)
        if length + added > _MAX_EXCERPT:
            break
        selected.append(line)
        length += added
    if not selected or not any(line.strip() for line in selected):
        return None
    return {"source": {"path": path, "line": start + 1,
                       "end_line": start + len(selected), "sha256": sha256},
            "excerpt": "\n".join(selected)}


def _online_keys(catalog) -> dict[str, list[str]]:
    if not isinstance(catalog, Mapping) or not isinstance(catalog.get("components"), Mapping):
        raise ValueError("framework_assembly_catalog_invalid")
    result = {}
    count = 0
    for rows in catalog["components"].values():
        if not isinstance(rows, list):
            raise ValueError("framework_assembly_catalog_invalid")
        for row in rows:
            count += 1
            if count > 256 or not isinstance(row, Mapping):
                raise ValueError("framework_assembly_catalog_invalid")
            key = row.get("key")
            if not isinstance(key, str) or len(key) > 120 or not _KEY.fullmatch(key):
                raise ValueError("framework_assembly_catalog_invalid")
            for identity in (key, row.get("catalog_key")):
                if isinstance(identity, str) and len(identity) <= 120 and _KEY.fullmatch(identity):
                    result.setdefault(identity, []).append(key)
    return {key: sorted(set(values)) for key, values in result.items()}


def _contract_evidence(query, unavailable):
    focused = {key for triggers, keys in _FOCUSED_CONTRACTS
               if any(_contains(query, term) for term in triggers) for key in keys}
    ranked = []
    for index, row in enumerate(_CONTRACTS):
        key, title, path, anchor, count, terms = row
        score = sum(4 for term in terms if _contains(query, term))
        if key == "framework_roles":
            score += 100  # Always retain the ownership map before details.
        if any(_contains(query, term) for term in _PRIORITY_CONTRACTS.get(key, ())):
            score += 20
        if key in focused:
            score += 60
        if key in _DEFAULTS:
            score += 1
        if not score:
            continue
        ranked.append((-score, index, row))
    evidence = []
    for _, _, row in sorted(ranked):
        if len(evidence) >= _MAX_CONTRACTS:
            break
        key, title, path, anchor, count, _ = row
        try:
            lines, digest = _read_source(path)
            start = next(i for i, line in enumerate(lines) if line.startswith(anchor))
            item = _excerpt(lines, digest, path, start, min(len(lines), start + count))
            if item is None:
                raise ValueError("empty_excerpt")
        except (OSError, UnicodeError, ValueError, StopIteration):
            unavailable.add(path)
            continue
        evidence.append({"id": "contract." + key, "title": title, **item})
    return evidence


def _catalog_evidence(query, online, unavailable):
    terms = _terms(query)
    preferred = {key for triggers, keys in _PREFERRED_COMPONENTS
                 if any(_contains(query, term) for term in triggers) for key in keys}
    ranked = []
    seen = set()
    for path in _ENTRY_FILES:
        try:
            lines, digest = _read_source(path)
        except (OSError, UnicodeError, ValueError):
            unavailable.add(path)
            continue
        starts = [i for i, line in enumerate(lines) if line.strip() == "[[entry]]"]
        for index, start in enumerate(starts):
            stop = starts[index + 1] if index + 1 < len(starts) else len(lines)
            try:
                parsed = tomllib.loads("\n".join(lines[start:stop]))["entry"]
                if len(parsed) != 1:
                    raise ValueError("ambiguous_entry")
                row = parsed[0]
                key, kind, title, summary = (row.get(name) for name in ("key", "kind", "title", "summary"))
                if (not isinstance(key, str) or not _KEY.fullmatch(key) or len(key) > 120
                        or kind not in {"adapter", "tool", "bias", "plugin", "representation", "solver", "problem"}
                        or not isinstance(title, str) or not isinstance(summary, str)):
                    continue
                if key in seen:
                    # Conflicting declarations must not silently create an owner.
                    unavailable.add("duplicate_catalog_key:" + key)
                    ranked = [item for item in ranked if item[2]["key"] != key]
                    continue
                seen.add(key)
                text = json.dumps(row, ensure_ascii=False).lower()
                score = sum(3 for term in terms if _contains(text, term))
                if key in preferred:
                    score += 35
                if _contains(query, key):
                    score += 100
                if _contains(query, title.lower()):
                    score += 30
                # A relevant offline component outranks an unrelated online one.
                if not terms and key in online:
                    score += 2
                snippet = _excerpt(lines, digest, path, start, stop)
                if snippet is None:
                    continue
                evidence = {"id": "catalog." + key, "key": key, "kind": kind,
                            "title": title[:240], "summary": summary[:600],
                            "online_bound": key in online,
                            "online_bindings": online.get(key, []), **snippet}
                ranked.append((-score, key, evidence))
            except (ValueError, KeyError, TypeError):
                unavailable.add(path)
    return [item[2] for item in sorted(ranked)[:_MAX_COMPONENTS]]


def build_framework_context(instruction, *, assembly_catalog, design_notes="") -> dict:
    """Retrieve current bounded facts; never import, build, or run a component.

    ``online_bound`` means only that an explicit workbench binding refers to a
    Catalog identity. It does not establish that every variant or parameter of
    the framework component can run online. The caller must still normalize
    every executable draft with its current assembly catalog.
    """
    query = _query(instruction, design_notes)
    online = _online_keys(assembly_catalog)
    unavailable = set()
    context = {"schema": SCHEMA, "evidence_level": "static_source",
               "catalog_authority": "source_local_read_only",
               "contracts": _contract_evidence(query, unavailable),
               "components": _catalog_evidence(query, online, unavailable),
               "limitations": [
                   "静态源码与声明证据，不是执行结果、算法正确性或数学证明；源码与文档可能需要进一步核对。",
                   "online_bound 仅表示当前实验台有显式映射；全部可执行参数和组合仍以 assembly_catalog 校验为准。",
                   "未绑定组件可以只读讨论与形成开发计划；检索不会执行组件、创建 Unit、访问数据库或模型。",
                   "只检索固定白名单；未命中不代表整个框架不存在该能力，也不执行运行时 Catalog profile 过滤。",
               ]}
    context["limitations"].extend("source_unavailable:" + path for path in sorted(unavailable))
    while len(json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_CONTEXT_BYTES:
        if context["components"]:
            context["components"].pop()
        elif len(context["contracts"]) > 1:
            context["contracts"].pop()
        else:
            raise ValueError("framework_context_too_large")
    return context


def evidence_keys(context) -> set[str]:
    """Validate the bounded evidence shape and return its citation identifiers.

    Shape validation is not a signature: an untrusted client could fabricate
    text and hashes. Only use server-generated context as trusted evidence;
    these identifiers never authorize an executable component or file access.
    """
    allowed = {"schema", "evidence_level", "catalog_authority", "contracts", "components", "limitations"}
    if (not isinstance(context, Mapping) or set(context) != allowed or context.get("schema") != SCHEMA
            or context.get("evidence_level") != "static_source"
            or context.get("catalog_authority") != "source_local_read_only"):
        raise ValueError("framework_evidence_invalid")
    try:
        size = len(json.dumps(context, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError("framework_evidence_invalid") from exc
    if size > MAX_CONTEXT_BYTES:
        raise ValueError("framework_evidence_invalid")
    limitations = context["limitations"]
    if (not isinstance(limitations, list) or len(limitations) > 40
            or any(not isinstance(item, str) or len(item) > 500 for item in limitations)):
        raise ValueError("framework_evidence_invalid")
    result = set()
    for name, count in (("contracts", _MAX_CONTRACTS), ("components", _MAX_COMPONENTS)):
        rows = context[name]
        if not isinstance(rows, list) or len(rows) > count:
            raise ValueError("framework_evidence_invalid")
        for row in rows:
            fields = {"id", "title", "source", "excerpt"}
            if name == "components":
                fields |= {"key", "kind", "summary", "online_bound", "online_bindings"}
            if not isinstance(row, Mapping) or set(row) != fields:
                raise ValueError("framework_evidence_invalid")
            identity = row["id"]
            if not isinstance(identity, str) or identity in result:
                raise ValueError("framework_evidence_invalid")
            if name == "contracts" and identity not in _CONTRACT_IDS:
                raise ValueError("framework_evidence_invalid")
            if name == "components":
                key = row["key"]
                if (not isinstance(key, str) or len(key) > 120 or not _KEY.fullmatch(key)
                        or identity != "catalog." + key or type(row["online_bound"]) is not bool
                        or not isinstance(row["online_bindings"], list) or len(row["online_bindings"]) > 256
                        or row["online_bound"] != bool(row["online_bindings"])
                        or any(not isinstance(binding, str) or len(binding) > 120 or not _KEY.fullmatch(binding)
                               for binding in row["online_bindings"])
                        or not isinstance(row["kind"], str) or not isinstance(row["summary"], str)
                        or len(row["summary"]) > 600):
                    raise ValueError("framework_evidence_invalid")
            source, excerpt = row["source"], row["excerpt"]
            if (not isinstance(row["title"], str) or not 1 <= len(row["title"]) <= 240
                    or not isinstance(source, Mapping) or set(source) != {"path", "line", "end_line", "sha256"}
                    or not isinstance(source["path"], str) or source["path"] not in _ALLOWED_PATHS
                    or type(source["line"]) is not int or source["line"] < 1
                    or type(source["end_line"]) is not int or source["end_line"] < source["line"]
                    or not isinstance(source["sha256"], str) or not _SHA.fullmatch(source["sha256"])
                    or not isinstance(excerpt, str) or not 1 <= len(excerpt) <= _MAX_EXCERPT
                    or len(excerpt.split("\n")) != source["end_line"] - source["line"] + 1):
                raise ValueError("framework_evidence_invalid")
            result.add(identity)
    return result


def verify_framework_sources(context) -> None:
    """Reject source drift between request preparation and model transport.

    This verifies only the selected source text, not an algorithm's behavior.
    Source paths remain the retriever's fixed whitelist; no client path is read.
    """
    evidence_keys(context)
    for row in context["contracts"] + context["components"]:
        source = row["source"]
        try:
            lines, digest = _read_source(source["path"])
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("framework_evidence_stale") from exc
        excerpt = "\n".join(lines[source["line"] - 1:source["end_line"]])
        if digest != source["sha256"] or excerpt != row["excerpt"]:
            raise ValueError("framework_evidence_stale")


def render_framework_facts(context, *, instruction="", design_notes="", max_chars=2200) -> dict:
    """Render a short source-only profile of the same retrieved context.

    Complete excerpts are kept or omitted, never shortened mid-rule. The full
    context and this profile share one retrieval index and one source verifier.
    No target answer, evaluation rubric or sample identifier is accepted here.
    """
    if type(max_chars) is not int or not 1200 <= max_chars <= 12000:
        raise ValueError("framework_facts_limit_invalid")
    verify_framework_sources(context)
    query = _query(instruction, design_notes)
    declarations = {"contract." + row[0]: row for row in _CONTRACTS}
    focused = {"contract." + key for triggers, names in _FOCUSED_CONTRACTS
               if any(_contains(query, term) for term in triggers) for key in names}
    contracts = []
    for row in context["contracts"]:
        declaration = declarations[row["id"]]
        score = sum(4 for term in declaration[5] if _contains(query, term))
        if row["id"] in focused:
            score += 60
        if any(_contains(query, term) for term in _PRIORITY_CONTRACTS.get(declaration[0], ())):
            score += 20
        if score:
            density = score / (1 + len(row["excerpt"]) / 1800)
            contracts.append((-density, len(row["excerpt"]), row["id"], row))
    # A small model needs the actual condition before general introductions.
    # Unmatched default material stays in the full production context only.
    selected = [row for _, _, _, row in sorted(contracts)]
    if not selected:
        selected = [row for row in context["contracts"] if row["id"] == "contract.framework_roles"]
    preferred = {key for triggers, names in _PREFERRED_COMPONENTS
                 if any(_contains(query, term) for term in triggers) for key in names}
    selected.extend(row for row in context["components"]
                    if row["key"] in preferred or _contains(query, row["key"]))
    header = "以下是按本次问题检索的当前框架资料；仅为静态依据，不能证明运行或授权。资料不足时明确待核对，不补造契约。\n"
    missing = [item.removeprefix("source_unavailable:") for item in context["limitations"]
               if item.startswith("source_unavailable:")]
    if missing:
        header += "资料不可用：" + "；".join(missing[:4]) + ("；其余见资料元数据。" if len(missing) > 4 else "。") + "\n"
    chunks = [header]
    evidence = []
    for row in selected:
        source = row["source"]
        # Catalog summaries are declarations owned by their TOML entry. Keep
        # the exact source excerpt in metadata, and do not copy wiring code
        # into the small cognition profile.
        excerpt = row["summary"] if row["id"].startswith("catalog.") else row["excerpt"]
        block = (f'[{row["id"]}] {source["path"]}:{source["line"]}\n{excerpt}\n')
        if sum(map(len, chunks)) + len(block) + len(chunks) > max_chars:
            continue
        chunks.append(block)
        evidence.append({"id": row["id"], "source": dict(source), "excerpt": row["excerpt"]})
    if not evidence:
        chunks.append("本次没有可用的完整资料；未命中不代表框架不存在该能力。")
    digest = hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return {"schema": "nsgablack.lab_framework_facts/v1", "text": "\n".join(chunks).strip(),
            "evidence": evidence, "limitations": list(context["limitations"]),
            "context_sha256": digest}


def build_framework_facts(instruction, *, assembly_catalog=None, design_notes="", max_chars=2200) -> dict:
    """Query-based short facts for both training and independent evaluation."""
    if assembly_catalog is None:
        from .lab_assembly import assembly_catalog as current_catalog
        assembly_catalog = current_catalog()
    return render_framework_facts(build_framework_context(
        instruction, assembly_catalog=assembly_catalog, design_notes=design_notes),
        instruction=instruction, design_notes=design_notes, max_chars=max_chars)
