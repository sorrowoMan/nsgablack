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
