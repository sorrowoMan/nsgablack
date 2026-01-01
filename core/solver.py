import time
import math
import random
import numpy as np
from scipy.spatial.distance import cdist
import json
import os

try:
    # 当作为包导入时使用相对导入
    from .base import BlackBoxProblem
    from .diversity import DiversityAwareInitializerBlackBox
    from .elite import AdvancedEliteRetention
    # 可选导入
    try:
        from ..utils.visualization import SolverVisualizationMixin
    except ImportError:
        try:
            # 从上级目录导入
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from utils.visualization import SolverVisualizationMixin
            # 移除添加的路径
            sys.path.pop(0)
        except ImportError:
            class SolverVisualizationMixin:
                def _init_visualization(self):
                    pass
    try:
        from ..bias import BiasModule
    except ImportError:
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bias import BiasModule
            sys.path.pop(0)
        except ImportError:
            BiasModule = None
    try:
        from ..utils.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
    except Exception:
        fast_is_dominated = None
        NUMBA_AVAILABLE = False
    try:
        from ..utils.experiment import ExperimentResult
    except ImportError:
        ExperimentResult = None
    try:
        from ..utils.representation import RepresentationPipeline
    except ImportError:
        RepresentationPipeline = None
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from base import BlackBoxProblem
    from diversity import DiversityAwareInitializerBlackBox
    from elite import AdvancedEliteRetention
    # 可选导入
    try:
        from utils.visualization import SolverVisualizationMixin
    except ImportError:
        class SolverVisualizationMixin:
            def _init_visualization(self):
                pass
    try:
        from bias import BiasModule
    except ImportError:
        BiasModule = None
    try:
        from utils.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
    except Exception:
        fast_is_dominated = None
        NUMBA_AVAILABLE = False
    try:
        from utils.experiment import ExperimentResult
    except ImportError:
        ExperimentResult = None
    try:
        from utils.representation import RepresentationPipeline
    except ImportError:
        RepresentationPipeline = None


class BlackBoxSolverNSGAII(SolverVisualizationMixin):
    def __init__(self, problem: BlackBoxProblem):
        self.enable_diversity_init = False
        self.use_history = False
        self.enable_elite_retention = True
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension
        # 约束相关：通过 problem.evaluate_constraints 统一计算违背度
        self.constraints = []  # 保留占位，兼容旧用法

        # Memory management
        self.memory_optimizer = None
        self.enable_memory_optimization = True
        self.temp_data = {}  # For temporary data that can be cleared
        self.constraint_violations = None
        self.var_bounds = problem.bounds
        # 偏向模块（奖函数+罚函数）
        self.bias_module: BiasModule = None
        self.enable_bias = False
        self.representation_pipeline: RepresentationPipeline = None
        self.pop_size = 80
        self.max_generations = 150
        self.crossover_rate = 0.85
        self.mutation_rate = 0.15
        self.initial_mutation_range = 0.8
        self.mutation_range = self.initial_mutation_range
        self.tol = 1e-5
        self.elite_retention_prob = 0.9
        self.diversity_params = {
            'candidate_size': 500,
            'similarity_threshold': 0.05,
            'rejection_prob': 0.6,
            'sampling_method': 'lhs',
            'save_history': True
        }
        self.population = None
        self.objectives = None
        self.pareto_solutions = None
        self.pareto_objectives = None
        self.generation = 0
        self.history = []
        self.running = False
        self.start_time = 0
        self.run_count = 0
        self.evaluation_count = 0
        self.enable_progress_log = True
        self.report_interval = 100
        self._maximize_report = False
        self.diversity_initializer = DiversityAwareInitializerBlackBox(
            problem,
            similarity_threshold=self.diversity_params['similarity_threshold'],
            rejection_prob=self.diversity_params['rejection_prob']
        )
        self.elite_manager = AdvancedEliteRetention(
            self.max_generations,
            self.pop_size,
            initial_retention_prob=self.elite_retention_prob,
            min_replace_ratio=0.05,
            max_replace_ratio=0.6,
            replacement_weights=None,
            enable_intelligent_history=True  # 启用智能历史管理
        )
        self.history_file = f"blackbox_{problem.name.replace(' ', '_')}_history.json"
        self.diversity_initializer.set_history_file(self.history_file)
        self.enable_convergence_detection = True
        self.convergence_params = {
            'stagnation_window': 20,
            'improvement_epsilon': 1e-4,
            'diversity_threshold': 0.08,
            'min_generations': 30,
            'noise_repeats': 3,
            'noise_std_threshold': 1e-6
        }
        self.convergence_state = {
            'status': 'INIT',
            'best_f_history': [],
            'stagnation_counter': 0,
            'diversity_history': [],
            'current_diversity': None,
            'best_idx': None,
            'best_x': None,
            'best_f': None,
            'noise_std': None,
            'last_update_gen': 0
        }
        self._init_visualization()

    def update_candidate_size(self, text):
        try:
            self.diversity_params['candidate_size'] = int(text)
        except Exception:
            pass

    def update_similarity_threshold(self, text):
        try:
            value = float(text)
            self.diversity_params['similarity_threshold'] = value
            self.diversity_initializer.similarity_threshold = value
        except Exception:
            pass

    def update_rejection_prob(self, text):
        try:
            value = float(text)
            self.diversity_params['rejection_prob'] = value
            self.diversity_initializer.rejection_prob = value
        except Exception:
            pass

    def update_pop_size(self, text):
        try:
            pop_size = int(text)
            adjusted = pop_size if pop_size % 2 == 0 else pop_size + 1
            self.pop_size = max(adjusted, 2 * self.num_objectives)
        except Exception:
            pass

    def update_max_generations(self, text):
        try:
            self.max_generations = int(text)
            self.elite_manager.max_generations = self.max_generations
        except Exception:
            pass

    def update_mutation_rate(self, value):
        self.mutation_rate = value

    def update_var_bound(self, var, bound_type, text):
        try:
            value = float(text)
            if bound_type == 'min':
                if value < self.var_bounds[var][1]:
                    self.var_bounds[var][0] = value
                else:
                    self.var_bounds[var][1] = value + 0.1
                    self.bound_textboxes[(var, 'max')].set_val(str(self.var_bounds[var][1]))
            else:
                if value > self.var_bounds[var][0]:
                    self.var_bounds[var][1] = value
                else:
                    self.var_bounds[var][0] = value - 0.1
                    self.bound_textboxes[(var, 'min')].set_val(str(self.var_bounds[var][0]))
            self.problem.bounds = self.var_bounds
            if self.plot_enabled:
                self.redraw_static_elements()
        except Exception:
            pass

    def run_algorithm(self, event):
        if not self.running:
            self.running = True
            self.start_time = time.time()
            self.evaluation_count = 0
            if self.population is None:
                self.initialize_population()
            self.update_pareto_solutions()
            if not self.history:
                self.record_history()
            self.start_animation()

    def stop_algorithm(self, event):
        self.running = False
        self.stop_animation()
        if self.enable_diversity_init and self.diversity_params.get('save_history', True):
            self.diversity_initializer.save_history()
        # 保存求解历史（包含每代的平均目标值）
        try:
            self.save_history()
        except Exception:
            pass
        # 保存智能历史数据
        try:
            intelligent_history_file = f"intelligent_{self.history_file}"
            self.elite_manager.save_intelligent_history(intelligent_history_file)
        except Exception:
            pass

    def reset(self, event):
        self.stop_algorithm(None)
        self.generation = 0
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self.pareto_solutions = None
        self.history = []
        self.mutation_range = self.initial_mutation_range
        self.evaluation_count = 0
        self.elite_manager = AdvancedEliteRetention(
            self.max_generations,
            self.pop_size,
            initial_retention_prob=self.elite_retention_prob
        )
        if self.plot_enabled:
            self.update_plot_dynamic()
        self.update_info_text()

    # ---- 约束与目标评估 ----
    def _evaluate_individual(self, x, individual_id=None):
        """评估单个个体的目标和约束违背度标量。

        目标来自 problem.evaluate(x)，约束来自 problem.evaluate_constraints(x)。
        约定 g(x) <= 0 为可行，g(x) > 0 为违反程度，这里将所有正违背度求和。
        """
        val = self.problem.evaluate(x)
        obj = np.asarray(val, dtype=float).flatten()

        try:
            cons = self.problem.evaluate_constraints(x)
            cons_arr = np.asarray(cons, dtype=float).flatten()
            violation = float(np.sum(np.maximum(cons_arr, 0.0))) if cons_arr.size > 0 else 0.0
        except Exception:
            cons_arr = np.zeros(0, dtype=float)
            violation = 0.0

        context = {
            "problem": self.problem,
            "constraints": cons_arr.tolist() if cons_arr.size > 0 else [],
            "constraint_violation": violation,
            "individual_id": individual_id,
        }

        # 应用 bias 模块
        if self.enable_bias and self.bias_module is not None:
            if self.num_objectives == 1:
                f_biased = self.bias_module.compute_bias(x, float(obj[0]), individual_id, context=context)
                obj = np.array([f_biased])
            else:
                # 多目标：对每个目标分别应用 bias
                obj_biased = []
                for i in range(len(obj)):
                    f_biased = self.bias_module.compute_bias(x, float(obj[i]), individual_id, context=context)
                    obj_biased.append(f_biased)
                obj = np.array(obj_biased)

        if cons_arr.size == 0 and "constraint_violation" in context:
            violation = float(context["constraint_violation"])

        return obj, violation

    def evaluate_population(self, population):
        """评估整个种群的目标和约束违背度。

        返回 (objectives, constraint_violations)。
        """
        pop_size = population.shape[0]
        objectives = np.zeros((pop_size, self.num_objectives))
        constraint_violations = np.zeros(pop_size, dtype=float)

        for i in range(pop_size):
            obj, vio = self._evaluate_individual(population[i], individual_id=i)
            if obj.size == self.num_objectives:
                objectives[i] = obj
            elif obj.size > self.num_objectives:
                objectives[i] = obj[: self.num_objectives]
            else:
                objectives[i, : obj.size] = obj
            constraint_violations[i] = vio
            self.evaluation_count += 1

        return objectives, constraint_violations

    def initialize_population(self):
        if self.enable_diversity_init:
            print("使用多样性感知初始化种群...")
            threshold, rejection_prob = self.diversity_initializer.adaptive_parameters(self.run_count)
            self.diversity_initializer.similarity_threshold = threshold
            self.diversity_initializer.rejection_prob = rejection_prob
            self.population, self.objectives = self.diversity_initializer.initialize_diverse_population(
                pop_size=self.pop_size,
                candidate_size=self.diversity_params['candidate_size'],
                sampling_method=self.diversity_params['sampling_method']
            )
            # 计算初始种群的约束违背度
            self.constraint_violations = np.zeros(self.population.shape[0], dtype=float)
            for i in range(self.population.shape[0]):
                try:
                    cons = self.problem.evaluate_constraints(self.population[i])
                    cons_arr = np.asarray(cons, dtype=float).flatten()
                    violation = float(np.sum(np.maximum(cons_arr, 0.0))) if cons_arr.size > 0 else 0.0
                except Exception:
                    violation = 0.0
                self.constraint_violations[i] = violation
        else:
            self.population = np.zeros((self.pop_size, self.dimension))
            if self.representation_pipeline is not None and self.representation_pipeline.initializer is not None:
                for i in range(self.pop_size):
                    context = {
                        'generation': self.generation,
                        'bounds': self.var_bounds
                    }
                    self.population[i] = self.representation_pipeline.init(self.problem, context)
            else:
                for i, var in enumerate(self.variables):
                    min_val, max_val = self.var_bounds[var]
                    self.population[:, i] = np.random.uniform(min_val, max_val, self.pop_size)
            self.objectives, self.constraint_violations = self.evaluate_population(self.population)

    def is_dominated_vectorized(self, obj_matrix):
        """非支配判定：优先使用 numba 加速版本，失败时回退到 numpy 实现。"""
        if obj_matrix.ndim == 1:
            obj = obj_matrix.reshape(-1, 1)
        else:
            obj = obj_matrix

        # 优先尝试 numba 加速实现
        if NUMBA_AVAILABLE and fast_is_dominated is not None:
            try:
                return fast_is_dominated(obj)
            except Exception:
                # 任意 numba 相关错误一律回退
                pass

        pop_size = obj.shape[0]
        dominated = np.zeros(pop_size, dtype=bool)
        for i in range(pop_size):
            less_equal = obj <= obj[i]
            strictly_less = obj < obj[i]
            dominates_mask = np.all(less_equal, axis=1) & np.any(strictly_less, axis=1)
            dominated[i] = np.any(dominates_mask)
        return dominated

    def non_dominated_sorting(self):
        """Optimized non-dominated sorting using O(MN²) algorithm"""
        try:
            # Import optimized fast non-dominated sort
            from ..utils.fast_non_dominated_sort import fast_non_dominated_sort_optimized, FastNonDominatedSort

            # Use optimized algorithm
            fronts, rank = fast_non_dominated_sort_optimized(
                self.objectives[:self.pop_size],
                self.constraint_violations[:self.pop_size]
            )

            # Calculate crowding distance only for the first front (and possibly others if needed)
            crowding_distance = np.zeros(self.pop_size)

            # Calculate crowding distance for all fronts for better diversity
            for front in fronts:
                if len(front) > 1:
                    front_distances = FastNonDominatedSort.calculate_crowding_distance(
                        self.objectives[:self.pop_size], front
                    )
                    for i, idx in enumerate(front):
                        if idx < self.pop_size:  # Ensure index is within bounds
                            crowding_distance[idx] = front_distances[idx]

            # Ensure we have the right number of ranks (handle edge cases)
            if len(rank) < self.pop_size:
                rank = np.pad(rank, (0, self.pop_size - len(rank)), 'constant', constant_values=len(fronts))

            return rank[:self.pop_size], crowding_distance[:self.pop_size], fronts

        except ImportError:
            # Fallback to original implementation if optimized version is not available
            return self._legacy_non_dominated_sorting()

    def _legacy_non_dominated_sorting(self):
        """Legacy non-dominated sorting implementation (O(N³) complexity)"""
        pop_size = self.population.shape[0]
        if self.constraint_violations is None:
            constraint_violations = np.zeros(pop_size, dtype=float)
        else:
            constraint_violations = np.asarray(self.constraint_violations, dtype=float)

        feasible_mask = constraint_violations <= 1e-10
        infeasible_mask = ~feasible_mask
        rank = np.zeros(pop_size, dtype=int)
        crowding_distance = np.zeros(pop_size)
        fronts = [[]]

        # Feasible solutions: classic non-dominated sorting
        feasible_indices = np.where(feasible_mask)[0]
        if feasible_indices.size > 0:
            feasible_objs = self.objectives[feasible_indices]
            dominated = self.is_dominated_vectorized(feasible_objs)
            first_front_feasible = feasible_indices[~dominated]
            fronts[0].extend(first_front_feasible.tolist())
            rank[first_front_feasible] = 0

        # Infeasible solutions: rank by constraint violation
        infeasible_indices = np.where(infeasible_mask)[0]
        if infeasible_indices.size > 0:
            sorted_infeasible = infeasible_indices[np.argsort(constraint_violations[infeasible_indices])]
            current_rank = 1 if len(fronts[0]) > 0 else 0
            for idx in sorted_infeasible:
                rank[idx] = current_rank
                current_rank += 1

        # Crowding distance calculation for feasible solutions only
        if feasible_indices.size > 0:
            for obj_idx in range(self.num_objectives):
                sorted_idx = feasible_indices[np.argsort(self.objectives[feasible_indices, obj_idx])]
                if len(sorted_idx) > 1:
                    crowding_distance[sorted_idx[0]] = np.inf
                    crowding_distance[sorted_idx[-1]] = np.inf
                    obj_range = self.objectives[sorted_idx[-1], obj_idx] - self.objectives[sorted_idx[0], obj_idx]
                    if obj_range > 1e-10 and len(sorted_idx) > 2:
                        # Safe crowding distance calculation
                        for i in range(1, len(sorted_idx) - 1):
                            if i + 1 < len(sorted_idx) and i - 1 >= 0:
                                crowding_distance[sorted_idx[i]] += (
                                    self.objectives[sorted_idx[i + 1], obj_idx] -
                                    self.objectives[sorted_idx[i - 1], obj_idx]
                                ) / obj_range
        return rank, crowding_distance, fronts

    def selection(self):
        parent_indices = np.zeros(self.pop_size, dtype=int)
        rank, crowding_distance, _ = self.non_dominated_sorting()
        i = np.random.randint(0, self.pop_size, self.pop_size)
        j = np.random.randint(0, self.pop_size, self.pop_size)
        mask = i == j
        j[mask] = np.random.randint(0, self.pop_size, np.sum(mask))
        rank_i = rank[i]
        rank_j = rank[j]
        crowd_i = crowding_distance[i]
        crowd_j = crowding_distance[j]
        parent_indices = np.where(
            rank_i < rank_j, i,
            np.where(rank_i > rank_j, j,
                     np.where(crowd_i >= crowd_j, i, j))
        )
        return self.population[parent_indices]

    def crossover(self, parents):
        pop_size = parents.shape[0]
        offspring = parents.copy()
        crossover_mask = np.random.rand(pop_size // 2) < self.crossover_rate
        alpha = np.random.rand(np.sum(crossover_mask), self.dimension)
        idx = 0
        for i in range(0, pop_size, 2):
            if i + 1 >= pop_size:
                break
            if crossover_mask[i // 2]:
                offspring[i] = alpha[idx] * parents[i] + (1 - alpha[idx]) * parents[i+1]
                offspring[i+1] = (1 - alpha[idx]) * parents[i] + alpha[idx] * parents[i+1]
                idx += 1
        return offspring

    def mutate(self, offspring):
        pop_size = offspring.shape[0]
        if self.representation_pipeline is not None and self.representation_pipeline.mutator is not None:
            for i in range(pop_size):
                context = {
                    'generation': self.generation,
                    'bounds': self.var_bounds
                }
                offspring[i] = self.representation_pipeline.mutate(offspring[i], context)
        else:
            mutation_mask = np.random.rand(pop_size) < self.mutation_rate
            mutation = np.random.uniform(-self.mutation_range, self.mutation_range, (pop_size, self.dimension))
            offspring[mutation_mask] += mutation[mutation_mask]
            for j, var in enumerate(self.variables):
                min_val, max_val = self.var_bounds[var]
                offspring[:, j] = np.clip(offspring[:, j], min_val, max_val)
            if self.representation_pipeline is not None and self.representation_pipeline.repair is not None:
                for i in range(pop_size):
                    context = {
                        'generation': self.generation,
                        'bounds': self.var_bounds
                    }
                    offspring[i] = self.representation_pipeline.repair.repair(offspring[i], context)
        return offspring

    def set_representation_pipeline(self, pipeline):
        """Attach a representation pipeline for encoding/repair/init/mutation."""
        self.representation_pipeline = pipeline

    def update_pareto_solutions(self):
        if self.objectives is None:
            return
        rank, _, _ = self.non_dominated_sorting()
        pareto_indices = np.where(rank == 0)[0]
        if len(pareto_indices) > 0:
            valid_indices = pareto_indices
            if len(valid_indices) > 50:
                valid_indices = valid_indices[:50]
            self.pareto_solutions = {
                'individuals': self.population[valid_indices],
                'objectives': self.objectives[valid_indices]
            }
            self.pareto_objectives = self.objectives[valid_indices]
        else:
            self.pareto_solutions = {'individuals': np.array([]), 'objectives': np.array([])}
            self.pareto_objectives = np.array([])

    def record_history(self):
        rank, _, _ = self.non_dominated_sorting()
        max_rank = min(2, np.max(rank) + 1)
        avg_objectives = []
        for r in range(max_rank):
            front_indices = np.where(rank == r)[0]
            if len(front_indices) == 0:
                avg_objectives.append(np.full(self.num_objectives, np.nan))
            else:
                avg_obj = np.mean(self.objectives[front_indices], axis=0)
                avg_objectives.append(avg_obj)
        self.history.append((self.generation, avg_objectives))

    def save_history(self):
        try:
            # Prepare serializable structure
            out = {
                'problem': getattr(self.problem, 'name', None),
                'generations': []
            }
            for gen, avg_objs in self.history:
                gen_entry = {'generation': int(gen), 'avg_objectives': []}
                for arr in avg_objs:
                    # arr may be numpy array or list
                    a = np.atleast_1d(arr)
                    vals = []
                    for v in a.tolist():
                        try:
                            if v is None:
                                vals.append(None)
                            else:
                                # convert nan to None
                                if isinstance(v, float) and np.isnan(v):
                                    vals.append(None)
                                else:
                                    vals.append(float(v))
                        except Exception:
                            vals.append(None)
                    gen_entry['avg_objectives'].append(vals)
                out['generations'].append(gen_entry)

            # Ensure directory exists if path contains one
            dirname = os.path.dirname(self.history_file)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            # Don't raise for save failures; keep running
            pass

    def _compute_population_diversity(self):
        if self.population is None or len(self.population) < 2:
            return 1.0
        # 使用 var_bounds 的键，而不是 self.variables，以确保匹配
        var_keys = list(self.var_bounds.keys())
        lows = np.array([self.var_bounds[v][0] for v in var_keys])
        highs = np.array([self.var_bounds[v][1] for v in var_keys])
        span = np.maximum(highs - lows, 1e-12)
        norm_pop = (self.population - lows) / span
        sample_size = min(30, norm_pop.shape[0])
        idx = np.random.choice(norm_pop.shape[0], sample_size, replace=False)
        sub = norm_pop[idx]
        distances = cdist(sub, sub)
        upper = distances[np.triu_indices_from(distances, k=1)]
        if upper.size == 0:
            return 1.0
        return float(np.mean(upper) / (math.sqrt(self.dimension) + 1e-12))

    def _reference_best_value(self):
        if self.objectives is None:
            return None, None
        if self.num_objectives == 1:
            best_idx = int(np.argmin(self.objectives[:, 0]))
            best_f = float(self.objectives[best_idx, 0])
        else:
            weights = np.linspace(1.0, 0.5, self.num_objectives)
            scores = np.sum(self.objectives * weights, axis=1)
            best_idx = int(np.argmin(scores))
            best_f = float(scores[best_idx])
        return best_idx, best_f

    def _evaluate_noise_std(self, x, repeats):
        try:
            values = []
            for _ in range(repeats):
                fx = self.problem.evaluate(x)
                fx_arr = np.atleast_1d(fx)
                val = float(fx_arr[0]) if fx_arr.size > 0 else float(fx)
                values.append(val)
            return float(np.std(values))
        except Exception:
            return None

    def update_convergence(self):
        if not self.enable_convergence_detection or self.objectives is None:
            return
        cs = self.convergence_state
        params = self.convergence_params
        best_idx, best_f = self._reference_best_value()
        if best_f is None:
            return
        cs['best_idx'] = best_idx
        cs['best_f'] = best_f
        cs['best_x'] = self.population[best_idx].copy()
        cs['best_f_history'].append(best_f)
        div = self._compute_population_diversity()
        cs['current_diversity'] = div
        cs['diversity_history'].append(div)
        hist = cs['best_f_history']
        window = params['stagnation_window']
        if len(hist) >= window:
            window_vals = hist[-window:]
            prev_best = min(window_vals[:-1])
            current_best = window_vals[-1]
            denom = max(abs(prev_best), 1.0)
            relative_improv = (prev_best - current_best) / denom
            if relative_improv < params['improvement_epsilon']:
                cs['stagnation_counter'] += 1
            else:
                cs['stagnation_counter'] = 0
        if self.generation < params['min_generations']:
            cs['status'] = 'EXPLORING'
        else:
            if cs['stagnation_counter'] == 0:
                cs['status'] = 'EXPLORING'
            elif cs['stagnation_counter'] < window // 2:
                cs['status'] = 'STAGNATING'
            else:
                if div <= params['diversity_threshold']:
                    if cs['noise_std'] is None:
                        cs['noise_std'] = self._evaluate_noise_std(cs['best_x'], params['noise_repeats'])
                    if cs['noise_std'] is None or cs['noise_std'] > params['noise_std_threshold']:
                        cs['status'] = 'NOISY_EXPLORING'
                    else:
                        cs['status'] = 'CONVERGED_CANDIDATE'
                else:
                    cs['status'] = 'STAGNATING'
        cs['last_update_gen'] = self.generation

    def get_convergence_info(self):
        return {
            'enabled': self.enable_convergence_detection,
            'params': self.convergence_params,
            'state': self.convergence_state.copy()
        }

    def _log_progress(self):
        if self.objectives is None or self.population is None:
            return
        try:
            if self.num_objectives == 1:
                best_idx = int(np.argmin(self.objectives[:, 0]))
                best_f = float(self.objectives[best_idx, 0])
                if getattr(self, "_maximize_report", False):
                    best_f_display = -best_f
                else:
                    best_f_display = best_f
                best_x = self.population[best_idx]
                print(
                    f"[进度] 第{self.generation}代 | 最优适应度: {best_f_display:.6f} | 最优解: {np.array2string(best_x, precision=6, separator=', ')}"
                )
            else:
                rank, _, _ = self.non_dominated_sorting()
                pareto_idx = np.where(rank == 0)[0]
                if len(pareto_idx) > 0:
                    sums = np.sum(self.objectives[pareto_idx], axis=1)
                    rep_rel = int(np.argmin(sums))
                    rep_idx = int(pareto_idx[rep_rel])
                    rep_obj = self.objectives[rep_idx]
                    rep_x = self.population[rep_idx]
                    print(
                        f"[进度] 第{self.generation}代 | Pareto解数: {len(pareto_idx)} | 代表目标: {np.array2string(rep_obj, precision=6, separator=', ')} | 解: {np.array2string(rep_x, precision=6, separator=', ')}"
                    )
                else:
                    print(f"[进度] 第{self.generation}代 | 暂无Pareto解")
        except Exception:
            pass

    def environmental_selection(self, combined_pop, combined_obj, combined_violations):
        combined_rank = np.zeros(len(combined_pop), dtype=int)
        feasible_mask = combined_violations <= 1e-10
        combined_rank[~feasible_mask] = 1
        if np.any(feasible_mask):
            feasible_objs = combined_obj[feasible_mask]
            dominated = self.is_dominated_vectorized(feasible_objs)
            combined_rank[feasible_mask] = np.where(dominated, 1, 0)
        combined_crowding = np.zeros(len(combined_pop))
        for r in [0, 1]:
            rank_mask = combined_rank == r
            if np.any(rank_mask):
                for obj_idx in range(self.num_objectives):
                    sorted_idx = np.argsort(combined_obj[rank_mask, obj_idx])
                    if len(sorted_idx) > 1:
                        obj_range = combined_obj[rank_mask, obj_idx][sorted_idx[-1]] - combined_obj[rank_mask, obj_idx][sorted_idx[0]]
                        if obj_range > 1e-10 and len(sorted_idx) > 2:
                            # Safe crowding distance calculation
                            rank_indices = np.where(rank_mask)[0]
                            for i in range(1, len(sorted_idx) - 1):
                                original_idx = rank_indices[sorted_idx[i]]
                                prev_obj = combined_obj[rank_mask, obj_idx][sorted_idx[i - 1]]
                                next_obj = combined_obj[rank_mask, obj_idx][sorted_idx[i + 1]]
                                combined_crowding[original_idx] += (next_obj - prev_obj) / obj_range
        sorted_indices = np.lexsort((-combined_crowding, combined_rank))
        self.population = combined_pop[sorted_indices[:self.pop_size]]
        self.objectives = combined_obj[sorted_indices[:self.pop_size]]
        self.constraint_violations = combined_violations[sorted_indices[:self.pop_size]]
        self.update_pareto_solutions()
        self.record_history()

    def evolve_one_generation(self):
        self.mutation_range = self.initial_mutation_range * (1 - self.generation / self.max_generations)
        parents = self.selection()
        offspring = self.crossover(parents)
        offspring = self.mutate(offspring)
        offspring_objectives, offspring_violations = self.evaluate_population(offspring)

        # 更新智能历史管理器
        diversity_metrics = {
            'population_diversity': self._compute_population_diversity(),
            'mutation_range': self.mutation_range
        }

        if self.enable_elite_retention and self.pareto_solutions is not None and len(self.pareto_solutions['individuals']) > 0:
            if self.num_objectives == 1:
                current_best = np.min(self.objectives)
            else:
                current_best = np.mean(self.pareto_solutions['objectives'][:, 0])
            elite_retention_prob = self.elite_manager.calculate_elite_retention_probability(
                self.generation, current_best, self.objectives, self.population
            )
            self.elite_manager.update_history(current_best)

            # 更新智能历史管理器的代际数据
            self.elite_manager.update_history_with_generation_data(
                self.generation, self.population, self.objectives, self.var_bounds, diversity_metrics
            )

            if random.random() > elite_retention_prob:
                elite_indices = np.where(self.non_dominated_sorting()[0] == 0)[0]
                if len(elite_indices) > 0:
                    ratio = self.elite_manager.get_elite_replacement_ratio(elite_retention_prob)
                    if len(elite_indices) > 1:
                        replace_count = int(np.ceil(len(elite_indices) * ratio))
                        replace_count = max(1, min(len(elite_indices) - 1, replace_count))
                    else:
                        replace_count = 0
                    if replace_count > 0:
                        replace_indices = np.random.choice(elite_indices, replace_count, replace=False)

                        # 检查是否应该使用智能历史替换
                        use_historical = self.elite_manager.should_use_historical_replacement(
                            self.generation, current_best
                        )

                        for i, idx in enumerate(replace_indices):
                            if use_historical and i < replace_count // 2:
                                # 使用智能历史管理器生成替换候选解
                                historical_candidates = self.elite_manager.get_historical_replacement_candidates(
                                    self.var_bounds, 1
                                )
                                if len(historical_candidates) > 0:
                                    new_individual = historical_candidates[0]
                                else:
                                    # 回退到随机生成
                                    new_individual = self._generate_random_individual()
                            else:
                                # 传统随机生成
                                new_individual = self._generate_random_individual()

                            self.population[idx] = new_individual
                            # 重新评估被替换个体
                            obj, vio = self._evaluate_individual(new_individual)
                            if obj.size == self.num_objectives:
                                self.objectives[idx] = obj
                            elif obj.size > self.num_objectives:
                                self.objectives[idx] = obj[: self.num_objectives]
                            else:
                                self.objectives[idx, : obj.size] = obj
                            if self.constraint_violations is None:
                                self.constraint_violations = np.zeros(self.pop_size, dtype=float)
                            self.constraint_violations[idx] = vio
        combined_pop = np.vstack([self.population, offspring])
        combined_obj = np.vstack([self.objectives, offspring_objectives])
        if self.constraint_violations is None:
            base_vio = np.zeros(self.population.shape[0], dtype=float)
        else:
            base_vio = np.asarray(self.constraint_violations, dtype=float)
        combined_violations = np.concatenate([base_vio, offspring_violations])
        self.environmental_selection(combined_pop, combined_obj, combined_violations)
        self.generation += 1
        self.update_convergence()
        if self.enable_progress_log and self.report_interval > 0 and (self.generation % self.report_interval == 0):
            self._log_progress()

    def _generate_random_individual(self):
        """生成随机个体"""
        new_individual = np.zeros(self.dimension)
        # 使用 var_bounds 的键，而不是 self.variables，以确保匹配
        var_keys = list(self.var_bounds.keys())
        for j, var in enumerate(var_keys):
            min_val, max_val = self.var_bounds[var]
            new_individual[j] = np.random.uniform(min_val, max_val)
        return new_individual

    def animate(self, frame):
        if not self.running or self.generation >= self.max_generations:
            self.running = False
            if self.enable_diversity_init and self.diversity_params.get('save_history', True):
                self.diversity_initializer.save_history()
            try:
                self.save_history()
            except Exception:
                pass
            # 保存智能历史数据
            try:
                intelligent_history_file = f"intelligent_{self.history_file}"
                self.elite_manager.save_intelligent_history(intelligent_history_file)
            except Exception:
                pass
            return

        self.evolve_one_generation()
        
        if self.plot_enabled and (self.generation - self.last_viz_update >= self.visualization_update_frequency):
            self.update_plot_dynamic()
            self.last_viz_update = self.generation
        self.update_info_text()
        if self.generation >= self.max_generations:
            self.run_count += 1

    def run(self, return_experiment=False):
        """非 GUI 模式运行

        Args:
            return_experiment: 如果为 True，返回 ExperimentResult 对象；否则返回字典
        """
        # Initialize memory optimization
        if self.enable_memory_optimization and self.memory_optimizer is None:
            try:
                from ..utils.memory_manager import OptimizationMemoryOptimizer
                self.memory_optimizer = OptimizationMemoryOptimizer(self)
                print("Memory optimization enabled")
            except ImportError:
                print("Memory optimization module not available")
                self.enable_memory_optimization = False

        self.running = True
        self.start_time = time.time()
        self.evaluation_count = 0
        if self.population is None:
            self.initialize_population()
        self.update_pareto_solutions()
        if not self.history:
            self.record_history()

        while self.running and self.generation < self.max_generations:
            self.evolve_one_generation()

            # Memory optimization every 10 generations
            if self.enable_memory_optimization and self.memory_optimizer and self.generation % 10 == 0:
                if self.generation % 50 == 0:  # Detailed optimization every 50 generations
                    self.memory_optimizer.auto_optimize()
                else:  # Light cleanup every 10 generations
                    self.memory_optimizer.memory_manager.cleanup_memory()

        self.running = False
        if self.enable_diversity_init and self.diversity_params.get('save_history', True):
            self.diversity_initializer.save_history()
        try:
            self.save_history()
        except Exception:
            pass
        # 保存智能历史数据
        try:
            intelligent_history_file = f"intelligent_{self.history_file}"
            self.elite_manager.save_intelligent_history(intelligent_history_file)
        except Exception:
            pass

        # Final memory cleanup
        if self.enable_memory_optimization and self.memory_optimizer:
            self.memory_optimizer.optimize_history_storage()
            self.memory_optimizer.clear_temporary_data()
        self.run_count += 1

        if return_experiment and ExperimentResult is not None:
            result = ExperimentResult(
                problem_name=getattr(self.problem, 'name', 'unknown'),
                config={
                    'pop_size': self.pop_size,
                    'max_generations': self.max_generations,
                    'crossover_rate': self.crossover_rate,
                    'mutation_rate': self.mutation_rate
                }
            )
            result.set_results(
                self.pareto_solutions['individuals'] if self.pareto_solutions else None,
                self.pareto_objectives,
                self.generation,
                self.evaluation_count,
                time.time() - self.start_time,
                self.history,
                self.get_convergence_info()
            )
            return result

        return {
            'pareto_solutions': self.pareto_solutions,
            'pareto_objectives': self.pareto_objectives,
            'generation': self.generation
        }
