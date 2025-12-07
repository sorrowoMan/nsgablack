import numpy as np
try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
    from ..solvers.nsga2 import BlackBoxSolverNSGAII
    from ..core.convergence import log_and_maybe_evaluate_convergence
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from core.base import BlackBoxProblem
    from solvers.nsga2 import BlackBoxSolverNSGAII
    from core.convergence import log_and_maybe_evaluate_convergence


class CallableSingleObjectiveProblem(BlackBoxProblem):
    """将任意单目标可调用函数适配为 BlackBoxProblem"""

    def __init__(self, objective, bounds, name="降维后单目标黑箱"):
        dimension = len(bounds)
        super().__init__(name=name, dimension=dimension,
                         bounds={f'x{i}': [float(low), float(high)] for i, (low, high) in enumerate(bounds)})
        self._objective = objective

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            return np.array([float(self._objective(xi)) for xi in x])
        return float(self._objective(x))

    def get_num_objectives(self):
        return 1


def run_headless_single_objective(objective, bounds, *,
                                  pop_size=80, max_generations=150,
                                  mutation_rate=0.15, crossover_rate=0.85,
                                  enable_diversity_init=False,
                                  enable_elite_retention=True,
                                  plot=False,
                                  maximize=False,
                                  use_history=False,
                                  history_file: str | None = None,
                                  seed_history_rate: float = 0.3,
                                  name="降维后单目标黑箱",
                                  convergence_log_file: str | None = None,
                                  evaluate_convergence: bool = False,
                                  evaluation_method: str = 'svm',
                                  evaluation_threshold: int = 30,
                                  min_replace_ratio: float | None = None,
                                  max_replace_ratio: float | None = None,
                                  replacement_weights: dict | None = None,
                                  show_progress: bool = True):
    if maximize:
        def _wrapped(x):
            return -float(objective(x))
        problem = CallableSingleObjectiveProblem(_wrapped, bounds, name=f"{name}(max→min)")
    else:
        problem = CallableSingleObjectiveProblem(objective, bounds, name=name)
    solver = BlackBoxSolverNSGAII(problem)
    solver.plot_enabled = bool(plot)
    solver.enable_diversity_init = bool(enable_diversity_init)
    solver.enable_elite_retention = bool(enable_elite_retention)
    solver.use_history = bool(use_history)
    solver._maximize_report = bool(maximize)
    solver.pop_size = int(pop_size)
    solver.max_generations = int(max_generations)
    solver.mutation_rate = float(mutation_rate)
    solver.crossover_rate = float(crossover_rate)
    if solver.enable_elite_retention:
        if min_replace_ratio is not None or max_replace_ratio is not None or replacement_weights is not None:
            solver.elite_manager.set_replacement_config(
                min_ratio=min_replace_ratio,
                max_ratio=max_replace_ratio,
                weights=replacement_weights
            )
    if history_file is not None:
        solver.history_file = history_file
        solver.diversity_initializer.set_history_file(history_file)
    if solver.enable_diversity_init and solver.use_history:
        solver.diversity_initializer.load_history()
    solver.running = True
    solver.initialize_population()
    if solver.enable_diversity_init and solver.use_history and seed_history_rate > 0:
        hist_solutions = solver.diversity_initializer.history_solutions
        if hist_solutions:
            try:
                dim = len(bounds)
                candidates = [np.array(s) for s in hist_solutions if len(s) == dim]
                if candidates:
                    scores = np.array([float(solver.problem.evaluate(s)) for s in candidates])
                    order = np.argsort(scores)
                    k = max(1, min(int(solver.pop_size * seed_history_rate), len(candidates)))
                    seeds = [candidates[i] for i in order[:k]]
                    k = min(k, solver.population.shape[0])
                    solver.population[:k] = np.vstack(seeds[:k])
                    solver.objectives = solver.evaluate_population(solver.population)
            except Exception:
                pass
    solver.update_pareto_solutions()
    solver.record_history()

    # 进度条支持：仅在非绘图模式下启用，且环境中安装了 tqdm
    if show_progress and not getattr(solver, "plot_enabled", False):
        try:
            from tqdm import trange  # type: ignore

            for _ in trange(solver.max_generations, desc="NSGA-II", unit="gen"):
                if not (solver.running and solver.generation < solver.max_generations):
                    break
                solver.animate(None)
        except Exception:
            while solver.running and solver.generation < solver.max_generations:
                solver.animate(None)
    else:
        while solver.running and solver.generation < solver.max_generations:
            solver.animate(None)
    if solver.objectives is not None and solver.objectives.ndim == 2:
        best_idx = int(np.argmin(solver.objectives[:, 0]))
        best_x = solver.population[best_idx]
        best_f = float(solver.objectives[best_idx, 0])
        if maximize:
            best_f = -best_f
    else:
        best_idx = None
        best_x = None
        best_f = None
    try:
        if solver.diversity_params.get('save_history', True):
            if solver.objectives is not None and solver.population is not None:
                scores = solver.objectives[:, 0]
                order = np.argsort(scores)
                top_k = max(1, min(10, solver.pop_size))
                for idx in order[:top_k]:
                    sol = solver.population[idx]
                    fit = float(scores[idx])
                    solver.diversity_initializer.add_to_history(sol, fit)
            if use_history:
                if solver.diversity_initializer.history_file is None and history_file is not None:
                    solver.diversity_initializer.set_history_file(history_file)
                solver.diversity_initializer.save_history()
    except Exception as e:
        print(f"保存历史时出现异常: {e}")
    eval_info = None
    try:
        if best_x is not None and evaluate_convergence:
            eval_info = log_and_maybe_evaluate_convergence(
                best_x, best_f, bounds,
                log_file=convergence_log_file,
                threshold=int(evaluation_threshold),
                method=str(evaluation_method).lower()
            )
    except Exception as _e:
        eval_info = {"evaluated": False, "error": f"评估异常: {_e}"}
    return {"x": best_x, "fun": best_f, "solver": solver, "evaluation": eval_info}
