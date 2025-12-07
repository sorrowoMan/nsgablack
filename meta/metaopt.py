import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Callable, List, Literal
from skopt.space import Real, Integer
try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer
    _SKOPT_AVAILABLE = True
except Exception:  # 作为降级方案
    _SKOPT_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    _MATPLOTLIB_AVAILABLE = True
except Exception:
    _MATPLOTLIB_AVAILABLE = False

try:
    import optuna
    _OPTUNA_AVAILABLE = True
except Exception:
    _OPTUNA_AVAILABLE = False

try:
    # 当作为包导入时使用相对导入
    from ..core.solver import BlackBoxSolverNSGAII
    from ..core.problems import BusinessPortfolioOptimization
    from ..utils.headless import run_headless_single_objective
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from core.solver import BlackBoxSolverNSGAII
    from core.problems import BusinessPortfolioOptimization
    from utils.headless import run_headless_single_objective

#cd "c:\Users\hp\Desktop\新建文件夹 (7)"
#python run_metaopt_engineering_compare.py
@dataclass
class SolverHyperParams:
    pop_size: int
    max_generations: int
    crossover_rate: float
    mutation_rate: float

    def apply_to(self, solver: BlackBoxSolverNSGAII) -> None:
        # 保证种群规模为偶数
        pop_size = int(self.pop_size)
        if pop_size % 2 == 1:
            pop_size += 1
        solver.pop_size = max(pop_size, 2 * solver.num_objectives)
        solver.max_generations = int(self.max_generations)
        solver.crossover_rate = float(self.crossover_rate)
        solver.mutation_rate = float(self.mutation_rate)


def default_search_space() -> Tuple[List[Any], Callable[[List[float]], SolverHyperParams]]:
    """定义一个针对 NSGA-II 的默认搜索空间（使用 skopt 的空间对象）。

    返回：
    - dimensions: skopt 的空间维度
    - decoder: 把 skopt 采样出的列表转换为 SolverHyperParams 的函数
    """
    # 种群大小、迭代代数、交叉率、变异率
    dimensions: List[Any] = [
        Integer(40, 200, name="pop_size"),
        Integer(50, 300, name="max_generations"),
        Real(0.6, 0.98, name="crossover_rate"),
        Real(0.02, 0.4, name="mutation_rate"),
    ]

    def decoder(x: List[float]) -> SolverHyperParams:
        return SolverHyperParams(
            pop_size=int(x[0]),
            max_generations=int(x[1]),
            crossover_rate=float(x[2]),
            mutation_rate=float(x[3]),
        )

    return dimensions, decoder


MetaObjective = Literal["single", "hypervolume", "weighted_sum", "eps_constraint"]
Backend = Literal["skopt", "tpe", "cma"]


def _aggregate_multiobjective(
    solver: BlackBoxSolverNSGAII,
    objective_type: MetaObjective = "single",
    weights: np.ndarray | None = None,
    reference_point: np.ndarray | None = None,
    eps: float | None = None,
) -> float:
    """根据多目标结果计算可用于元优化的标量指标。

    - "single": 若问题本身是单目标，则直接返回最优值；多目标时对目标求和后取最小。
    - "weighted_sum": 使用给定权重对目标做加权和，再取最小。
    - "hypervolume": 计算近似 Hypervolume（此处实现为简单的参考点主导体积近似）。
    - "eps_constraint": 以第一个目标为主，将其余目标约束在 eps 以内，否则加罚项。
    返回值始终是 *需要最小化的损失*。
    """
    if solver.objectives is None or len(solver.objectives) == 0:
        return float("inf")

    objs = np.asarray(solver.objectives, dtype=float)
    m = objs.shape[1]

    if objective_type == "single":
        if m == 1:
            return float(np.min(objs[:, 0]))
        scores = np.sum(objs, axis=1)
        return float(np.min(scores))

    if objective_type == "weighted_sum":
        if weights is None:
            weights = np.ones(m, dtype=float) / m
        w = np.asarray(weights, dtype=float).reshape(1, -1)
        scores = np.sum(objs * w, axis=1)
        return float(np.min(scores))

    if objective_type == "eps_constraint":
        if m == 1:
            return float(np.min(objs[:, 0]))
        if eps is None:
            eps = 0.0
        # 以第 0 个目标为主目标，其余目标若超过 eps 则补充罚项
        main = objs[:, 0].copy()
        for j in range(1, m):
            viol = np.maximum(0.0, objs[:, j] - eps)
            main += 1e3 * viol
        return float(np.min(main))

    if objective_type == "hypervolume":
        # 简单 Hypervolume 近似：对非支配前沿用参考点计算体积
        if reference_point is None:
            ref = np.max(objs, axis=0) + 1.0
        else:
            ref = np.asarray(reference_point, dtype=float)
        # 只取非支配解
        dominated = solver.is_dominated_vectorized(objs)
        front = objs[~dominated]
        if len(front) == 0:
            return float("inf")
        # 非严格 HV 实现：对每个解计算长方体体积并使用 Inclusion-Exclusion 简单近似
        # 为保证简洁，这里仅对不同解体积求和，可能高估 HV，但可用于相对比较
        volumes = np.prod(np.maximum(0.0, ref - front), axis=1)
        hv = float(np.sum(volumes))
        # 元优化目标是“越小越好”，因此取负数
        return -hv

    # 默认退回 single
    return float(np.min(objs[:, 0]))


def _build_objective_fn(
    base_problem_factory: Callable[[], Any],
    search_space_decoder: Callable[[List[float]], SolverHyperParams],
    n_repeats: int = 1,
    random_seed: int | None = None,
    objective_type: MetaObjective = "single",
    weights: np.ndarray | None = None,
    reference_point: np.ndarray | None = None,
    eps: float | None = None,
) -> Callable[[List[float]], float]:
    """构造元优化的目标函数，支持多目标汇总策略。"""

    def objective(x: List[float]) -> float:
        hp = search_space_decoder(x)
        losses: List[float] = []
        for repeat in range(max(1, n_repeats)):
            if random_seed is not None:
                np.random.seed(random_seed + repeat)
            problem = base_problem_factory()
            solver = BlackBoxSolverNSGAII(problem)
            # 在元优化场景下关闭多样性初始化，避免每次评估 500 个候选解
            solver.enable_diversity_init = False
            solver.enable_elite_retention = False  # 精英保留也可以关掉，加快速度
            solver.enable_progress_log = False
            solver.enable_convergence_detection = False
            hp.apply_to(solver)

            # 统一用 solver 自己跑若干代，而不是依赖 headless API
            if solver.population is None:
                solver.initialize_population()
            max_gen_backup = solver.max_generations
            # 为加快元优化，每次只跑较少代数
            solver.max_generations = min(solver.max_generations, 20)
            # 强制无 GUI 模式迭代
            while solver.generation < solver.max_generations:
                solver.animate(None)
                if solver.generation % 5 == 0:
                    print(f"[metaopt] 当前代数: {solver.generation}")
                if solver.generation >= solver.max_generations:
                    break
            solver.max_generations = max_gen_backup

            # 单目标或多目标统一用聚合函数计算损失
            loss = _aggregate_multiobjective(
                solver,
                objective_type=objective_type,
                weights=weights,
                reference_point=reference_point,
                eps=eps,
            )
            losses.append(float(loss))
        return float(np.mean(losses))

    return objective


def bayesian_meta_optimize(
    base_problem_factory: Callable[[], Any] | None = None,
    n_calls: int = 20,
    n_initial_points: int = 5,
    n_repeats: int = 1,
    random_seed: int | None = 42,
    objective_type: MetaObjective = "single",
    weights: np.ndarray | None = None,
    reference_point: np.ndarray | None = None,
    eps: float | None = None,
    backend: Backend = "skopt",
) -> Dict[str, Any]:
    """自动搜索 NSGA-II 超参数的元优化接口。

    - backend="skopt": 使用高斯过程贝叶斯优化 (gp_minimize)
    - backend="tpe": 使用 Optuna 的 TPE 采样
    - backend="cma": 使用 Optuna 的 CMA-ES 采样

    objective_type 用于多目标汇总："single" / "weighted_sum" / "hypervolume" / "eps_constraint"。
    """

    if base_problem_factory is None:
        def base_problem_factory() -> Any:
            return BusinessPortfolioOptimization(dimension=5)

    dimensions, decoder = default_search_space()
    objective = _build_objective_fn(
        base_problem_factory,
        decoder,
        n_repeats=n_repeats,
        random_seed=random_seed,
        objective_type=objective_type,
        weights=weights,
        reference_point=reference_point,
        eps=eps,
    )

    history: List[Dict[str, Any]] = []

    def record_and_return(loss: float, x: List[float]) -> None:
        hp = decoder(x)
        history.append({
            "params": {
                "pop_size": hp.pop_size,
                "max_generations": hp.max_generations,
                "crossover_rate": hp.crossover_rate,
                "mutation_rate": hp.mutation_rate,
            },
            "loss": float(loss),
        })

    if backend == "skopt":
        if not _SKOPT_AVAILABLE:
            raise RuntimeError("需要安装 scikit-optimize (skopt) 才能使用 skopt 后端。")

        def wrapped_objective(x: List[float]) -> float:
            loss = objective(x)
            record_and_return(loss, x)
            return loss

        res = gp_minimize(
            wrapped_objective,
            dimensions=dimensions,
            n_calls=n_calls,
            n_initial_points=n_initial_points,
            random_state=random_seed,
            acq_func="EI",
        )
        best_hp = decoder(res.x)
        backend_result = res

    elif backend in ("tpe", "cma"):
        if not _OPTUNA_AVAILABLE:
            raise RuntimeError("需要安装 optuna 才能使用 TPE/CMA-ES 后端。请安装 'optuna'。")

        sampler: optuna.samplers.BaseSampler
        if backend == "tpe":
            sampler = optuna.samplers.TPESampler(seed=random_seed)
        else:
            sampler = optuna.samplers.CmaEsSampler(seed=random_seed)

        study = optuna.create_study(direction="minimize", sampler=sampler)

        def objective_optuna(trial: optuna.trial.Trial) -> float:
            x = [
                trial.suggest_int("pop_size", 40, 200),
                trial.suggest_int("max_generations", 50, 300),
                trial.suggest_float("crossover_rate", 0.6, 0.98),
                trial.suggest_float("mutation_rate", 0.02, 0.4),
            ]
            loss = objective(x)
            record_and_return(loss, x)
            return loss

        study.optimize(objective_optuna, n_trials=n_calls)
        best_trial = study.best_trial
        x_best = [
            int(best_trial.params["pop_size"]),
            int(best_trial.params["max_generations"]),
            float(best_trial.params["crossover_rate"]),
            float(best_trial.params["mutation_rate"]),
        ]
        best_hp = decoder(x_best)
        backend_result = study

    else:
        raise ValueError(f"不支持的 backend: {backend}")

    return {
        "best_params": best_hp,
        "best_loss": float(min(h["loss"] for h in history)) if history else float("inf"),
        "backend_result": backend_result,
        "history": history,
    }


def plot_metaopt_history(history: List[Dict[str, Any]]) -> None:
    """简单可视化：画出 loss 随试验编号的变化，以及各超参数 vs loss。

    若未安装 matplotlib，则直接返回。
    """
    if not _MATPLOTLIB_AVAILABLE or not history:
        return

    losses = [h["loss"] for h in history]
    pop_sizes = [h["params"]["pop_size"] for h in history]
    max_gens = [h["params"]["max_generations"] for h in history]
    cross_rates = [h["params"]["crossover_rate"] for h in history]
    mut_rates = [h["params"]["mutation_rate"] for h in history]

    fig, axes = plt.subplots(2, 3, figsize=(12, 6))
    ax0 = axes[0, 0]
    ax0.plot(range(1, len(losses) + 1), losses, marker="o")
    ax0.set_xlabel("试验编号")
    ax0.set_ylabel("损失 (loss)")
    ax0.set_title("Meta-Opt 损失收敛曲线")

    def _scatter(ax, xs, ys, xlabel, title):
        ax.scatter(xs, ys, s=25, alpha=0.7)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("loss")
        ax.set_title(title)

    _scatter(axes[0, 1], pop_sizes, losses, "pop_size", "pop_size vs loss")
    _scatter(axes[0, 2], max_gens, losses, "max_generations", "max_generations vs loss")
    _scatter(axes[1, 0], cross_rates, losses, "crossover_rate", "crossover_rate vs loss")
    _scatter(axes[1, 1], mut_rates, losses, "mutation_rate", "mutation_rate vs loss")
    axes[1, 2].axis("off")
    plt.tight_layout()
    plt.show()


def quick_demo_metaopt() -> None:
    """快速示例：对投资组合问题进行元优化，并对比 skopt/TPE。"""

    def factory() -> Any:
        return BusinessPortfolioOptimization(dimension=5)

    print("使用 skopt 后端 (GP) 进行元优化...")
    result_gp = bayesian_meta_optimize(
        base_problem_factory=factory,
        n_calls=15,
        n_initial_points=5,
        n_repeats=1,
        random_seed=123,
        objective_type="weighted_sum",
    )

    best_gp = result_gp["best_params"]
    print("\n[Meta-Opt / skopt] 最优超参数：")
    print(f"  pop_size        = {best_gp.pop_size}")
    print(f"  max_generations = {best_gp.max_generations}")
    print(f"  crossover_rate  = {best_gp.crossover_rate:.4f}")
    print(f"  mutation_rate   = {best_gp.mutation_rate:.4f}")
    print(f"  best loss       = {result_gp['best_loss']:.6f}")

    try:
        print("\n使用 TPE 后端进行对比元优化...")
        result_tpe = bayesian_meta_optimize(
            base_problem_factory=factory,
            n_calls=15,
            n_initial_points=5,
            n_repeats=1,
            random_seed=123,
            objective_type="weighted_sum",
            backend="tpe",
        )
        best_tpe = result_tpe["best_params"]
        print("\n[Meta-Opt / TPE] 最优超参数：")
        print(f"  pop_size        = {best_tpe.pop_size}")
        print(f"  max_generations = {best_tpe.max_generations}")
        print(f"  crossover_rate  = {best_tpe.crossover_rate:.4f}")
        print(f"  mutation_rate   = {best_tpe.mutation_rate:.4f}")
        print(f"  best loss       = {result_tpe['best_loss']:.6f}")
    except RuntimeError as e:
        print("[Meta-Opt] TPE 后端不可用:", e)
        result_tpe = None

    # 简单画一张 history 图（以 skopt 的为主）
    print("\n绘制元优化搜索历史图...")
    plot_metaopt_history(result_gp["history"])
