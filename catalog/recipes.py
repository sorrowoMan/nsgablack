"""Recipe classification and constructor checks; no component is instantiated."""
import ast
import inspect


ADAPTER_RECIPES = {
    "adapter.composite": (
        "from nsgablack.adapters import CompositeAdapter, NSGA2Adapter",
        "solver.set_adapter(CompositeAdapter(adapters=[NSGA2Adapter(population_size=4, offspring_size=4)]))",
    ),
    "adapter.role": (
        "from nsgablack.adapters import RoleAdapter, NSGA2Adapter",
        "solver.set_adapter(RoleAdapter(role='explorer', inner=NSGA2Adapter(population_size=4, offspring_size=4)))",
    ),
    "adapter.multi_role_controller": (
        "from nsgablack.adapters import RoleAdapter, NSGA2Adapter",
        "from nsgablack.adapters.role_adapters import MultiRoleControllerAdapter",
        "roles = [RoleAdapter(role='explorer', inner=NSGA2Adapter(population_size=4, offspring_size=4))]",
        "solver.set_adapter(MultiRoleControllerAdapter(roles=roles))",
    ),
    "adapter.astar": (
        "import numpy as np",
        "from nsgablack.adapters import AStarAdapter",
        "def neighbors(state, context):",
        "    return [np.asarray(state) + 0.1]",
        "solver.set_adapter(AStarAdapter(neighbors=neighbors, start_state=np.zeros(solver.problem.dimension)))",
    ),
    "adapter.moa_star": (
        "import numpy as np",
        "from nsgablack.adapters import MOAStarAdapter",
        "def neighbors(state, context):",
        "    return [np.asarray(state) + 0.1]",
        "solver.set_adapter(MOAStarAdapter(neighbors=neighbors, start_state=np.zeros(solver.problem.dimension)))",
    ),
    # Existing per-key overrides also prevent unsupported legacy components
    # from being inferred as normal constructor/add recipes. Keep these tuples
    # nonempty and entirely explanatory; no component is assembled by them.
    "bias.diversity": (
        "# 旧 DiversityBias 依赖单种群 population_ref，没有明确 Unit 实例的正式装配配方。",
        "# 迁移说明：docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md（旧类未装配）。",
        "# bias.unit_preference / bias.population_diversity 提供显式欧氏最近邻偏好，不等价替代旧类全部距离度量或历史统计。",
    ),
    "bias.diversity_adaptive": (
        "# 旧 AdaptiveDiversityBias 的方向、重复加权和参考绑定待迁移；此处不构造或挂载旧类。",
        "# 当前边界：docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md。",
        "# bias.unit_preference / bias.population_diversity 是明确 Unit 的固定权重最近邻路径，不等价于自适应公式。",
    ),
    "bias.diversity_crowding": (
        "# 旧 CrowdingDistanceBias 的方向、重复加权、非有限值和参考绑定尚未形成正常稀疏奖励配方。",
        "# 当前边界：docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md（旧类未装配）。",
        "# bias.unit_preference / bias.population_diversity 可绑定最近邻新颖性，不等价于 k 邻域均值或 NSGA2 拥挤距离。",
    ),
    "bias.diversity_sharing": (
        "# 旧 SharingFunctionBias 的倒数公式、重复加权、身份与参考依赖待迁移；此处不挂载旧类。",
        "# 当前边界：docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md。",
        "# bias.unit_preference / bias.population_diversity 提供显式 Unit 最近邻偏好，不等价于 sigma_share/alpha 共享核。",
    ),
    "bias.diversity_niche": (
        "# 旧 NicheDiversityBias 缺少正式成员维护、提交恢复和正确最小化方向；此处不构造或挂载旧类。",
        "# 当前边界：docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md。",
        "# bias.unit_preference / bias.population_diversity 可用于显式 Unit 新颖性或观察，不等价于生态位计数或容量约束。",
    ),
}


def constructor_check(entry, lines):
    """Return (status, reasons): syntax/signature checks are not execution proofs."""
    source = "\n".join(lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "guidance", ("说明文字，不是可执行 Python 配方",)
    if any(isinstance(n, ast.Constant) and n.value is Ellipsis for n in ast.walk(tree)):
        return "template", ("需要填写省略的组件或参数",)
    try:
        symbol = entry.load()
        signature = inspect.signature(symbol)
    except Exception as exc:
        return "unverified", (f"签名不可验证: {type(exc).__name__}",)
    symbol_name = str(entry.import_path).split(":")[-1].split(".")[-1]
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
             isinstance(n.func, (ast.Name, ast.Attribute)) and
             (n.func.id if isinstance(n.func, ast.Name) else n.func.attr) == symbol_name]
    if not calls:
        return "guidance", ("片段未直接构造该组件",)
    for call in calls:
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            return "template", ("展开参数须由调用者提供",)
        try:
            signature.bind(*([object()] * len(call.args)), **{k.arg: object() for k in call.keywords})
        except TypeError as exc:
            return "invalid", (str(exc),)
    return "signature-checked", ("仅通过语法和构造签名检查；不等于行为已验证",)


def required_arguments(entry):
    try:
        signature = inspect.signature(entry.load())
    except (ImportError, ValueError, TypeError, AttributeError):
        return ()
    return tuple(p for p in signature.parameters.values()
                 if p.default is inspect.Parameter.empty and
                 p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD))
