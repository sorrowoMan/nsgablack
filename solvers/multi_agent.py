"""
多智能体黑盒求解器

基于NSGA-II框架实现的多智能体协同进化求解器
通过不同角色的智能体实现探索、开发、学习和协调

智能体角色：
- Explorer: 探索者，专注于发现新区域
- Exploiter: 开发者，专注于局部优化
- Waiter: 等待者，学习其他智能体的成功模式
- Coordinator: 协调者，动态调整策略
"""

import time
import os
import json
from typing import List, Dict, Tuple

import numpy as np

try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
    from ..core.solver import BaseSolver
    from ..multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config
    from ..multi_agent.core.population import AgentPopulation
    from ..multi_agent.components import (
        AdvisorMixin,
        ArchiveMixin,
        CommunicationMixin,
        EvolutionMixin,
        RegionMixin,
        RoleLogicMixin,
        ScoringMixin,
        UtilsMixin,
    )
    # 可选导入
    try:
        from ..utils.visualization import SolverVisualizationMixin
    except ImportError:
        class SolverVisualizationMixin:
            pass
    try:
        from ..bias import BiasModule
    except ImportError:
        BiasModule = None
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
    try:
        from nsgablack.core.base import BlackBoxProblem
        from nsgablack.core.solver import BaseSolver
        from nsgablack.multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config
        from nsgablack.multi_agent.core.population import AgentPopulation
        from nsgablack.multi_agent.components import (
            AdvisorMixin,
            ArchiveMixin,
            CommunicationMixin,
            EvolutionMixin,
            RegionMixin,
            RoleLogicMixin,
            ScoringMixin,
            UtilsMixin,
        )
    except ImportError:
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        core_dir = os.path.join(parent_dir, 'core')
        utils_dir = os.path.join(parent_dir, 'utils')
        multi_agent_dir = os.path.join(parent_dir, 'multi_agent')
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)
        if utils_dir not in sys.path:
            sys.path.insert(0, utils_dir)
        if multi_agent_dir not in sys.path:
            sys.path.insert(0, multi_agent_dir)
        from base import BlackBoxProblem
        from base_solver import BaseSolver
        from multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config
        from multi_agent.core.population import AgentPopulation
        from multi_agent.components import (
            AdvisorMixin,
            ArchiveMixin,
            CommunicationMixin,
            EvolutionMixin,
            RegionMixin,
            RoleLogicMixin,
            ScoringMixin,
            UtilsMixin,
        )

    # 可选导入
    try:
        from nsgablack.utils.visualization import SolverVisualizationMixin
    except ImportError:
        class SolverVisualizationMixin:
            pass
    try:
        from nsgablack.bias import BiasModule
    except ImportError:
        BiasModule = None
    try:
        from nsgablack.utils.experiment import ExperimentResult
    except ImportError:
        ExperimentResult = None
    try:
        from nsgablack.utils.representation import RepresentationPipeline
    except ImportError:
        RepresentationPipeline = None


class MultiAgentBlackBoxSolver(
    UtilsMixin,
    EvolutionMixin,
    RoleLogicMixin,
    AdvisorMixin,
    ArchiveMixin,
    ScoringMixin,
    RegionMixin,
    CommunicationMixin,
    BaseSolver,
    SolverVisualizationMixin,
):
    """
    多智能体黑盒求解器

    基于NSGA-II框架，通过多智能体协同进化进行优化。
    每个智能体角色有不同的搜索策略和偏置设置。
    """

    def __init__(self, problem: BlackBoxProblem, config: Dict = None):
        """初始化多智能体求解器"""
        # 调用父类初始化
        super().__init__(problem)

        # 基础属性
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension
        self.constraints = []
        self.constraint_violations = None
        self.var_bounds = self._normalize_bounds(problem.bounds)

        # 默认配置
        self.config = {
            'total_population': 200,
            'agent_ratios': {
                AgentRole.EXPLORER: 0.25,    # 25% 探索者
                AgentRole.EXPLOITER: 0.35,   # 35% 开发者
                AgentRole.WAITER: 0.15,      # 15% 等待者
                AgentRole.ADVISOR: 0.15,      # 15% 建议者 🌟
                AgentRole.COORDINATOR: 0.10  # 10% 协调者
            },
            'max_generations': 100,
            'elite_ratio': 0.1,
            'communication_interval': 5,     # 种群间通信间隔
            'adaptation_interval': 20,       # 策略调整间隔
            'dynamic_ratios': True,          # 是否动态调整比例
            'role_score_weights': {          # scoring weights for role adaptation
                'improvement': 0.5,
                'feasibility': 0.3,
                'diversity': 0.2
            },
            'global_score_biases': [],
            'role_score_biases': {},
            'ratio_update_rate': 0.2,        # how fast ratios move toward target
            'min_role_ratio': 0.05,
            'max_role_ratio': 0.6,
            'use_bias_system': True,         # 是否使用偏置系统
            'region_partition': False,       # 是否启用区域分区（生产调度特有）
            'advisory_method': 'bayesian',   # 建议者使用的方法: 'bayesian', 'ml', 'ensemble'
            'advisory_update_interval': 5,   # 建议更新间隔
            'advisor_injection_interval': 1,
            'advisor_injection_k': 2,
            'advisor_injection_jitter': 0.0,
            'advisor_injection_roles': [AgentRole.EXPLORER, AgentRole.EXPLOITER],
            'advisor_candidate_pool': 4,
            'advisor_candidate_sources': ['archive', 'random', 'bayesian'],
            'advisor_candidate_source_weights': {},
            'advisor_score_biases': [],
            'advisor_score_use_constraints': True,
            'advisor_score_use_objectives': False,
            'waiter_reassign_interval': 1,
            'waiter_reassign_ratio': 0.2,
            'waiter_reassign_targets': None,
            'archive_enabled': True,
            'archive_size': 200,
            'archive_sizes': None,           # optional per-archive sizes
            'archive_share_k': 3,
            'archive_inject_jitter': 0.01,
            'archive_seed_ratio': 0.5,
            'region_update_interval': None,
            'region_top_ratio': 0.2,
            'region_expansion': 0.2,
            'region_min_expansion': 0.05,
            'region_role_factors': None,
            'region_violation_weight': 1000.0,
            'representation_pipeline': None,
            'representation_pipelines': {}
        }

        # 更新配置
        if config:
            self.config.update(config)

        # 初始化智能体种群
        self.agent_populations = {}
        self._initialize_agents()

        # 历史记录
        self.history = {
            'best_objectives': [],
            'diversity': [],
            'convergence_rate': [],
            'agent_contributions': {role: [] for role in AgentRole},
            'agent_scores': {role: [] for role in AgentRole},
            'archive_sizes': {
                'feasible': [],
                'boundary': [],
                'diversity': []
            },
            'generation': 0
        }

        # 全局最优
        self.global_best = None
        self.global_best_objectives = None
        self.global_best_constraints = None

        # 统计信息
        self.stats = {
            'evaluations': 0,
            'communications': 0,
            'adaptations': 0
        }
        self.enable_selection_trace = False
        self.selection_trace_path = None
        self.selection_trace_mode = "full"
        self.selection_trace_limit = None
        self.selection_trace_stride = 1
        self.selection_trace_flush_interval = 1
        self.selection_trace_buffer = []

        # global archives for information sharing
        self.archives = {
            'feasible': [],
            'boundary': [],
            'diversity': []
        }
        # backward compatible alias (feasible archive)
        self.archive = self.archives['feasible']

        print(f"[MultiAgent] 初始化多智能体求解器")
        print(f"[MultiAgent] 种群配置: {[f'{role.value}: {len(pop.population)}' for role, pop in self.agent_populations.items()]}")

    def enable_selection_tracing(self, path=None, mode="full", max_records=None, stride=1, flush_interval=1):
        """Enable selection tracing and write per-generation decisions to a JSONL file."""
        self.enable_selection_trace = True
        self.selection_trace_mode = mode
        self.selection_trace_limit = max_records
        self.selection_trace_stride = max(1, int(stride))
        self.selection_trace_flush_interval = max(1, int(flush_interval))
        self.selection_trace_buffer = []
        if path is None:
            safe_name = getattr(self.problem, "name", "problem").replace(" ", "_")
            trace_dir = os.path.join("reports", "selection_trace")
            os.makedirs(trace_dir, exist_ok=True)
            path = os.path.join(trace_dir, f"selection_trace_multi_agent_{safe_name}.jsonl")
        else:
            trace_dir = os.path.dirname(path)
            if trace_dir:
                os.makedirs(trace_dir, exist_ok=True)
        self.selection_trace_path = path
        try:
            with open(self.selection_trace_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    def disable_selection_tracing(self):
        """Disable selection tracing."""
        self._flush_selection_trace()
        self.enable_selection_trace = False

    def _should_trace_selection(self):
        if not self.enable_selection_trace:
            return False
        stride = max(1, int(self.selection_trace_stride))
        return (self.history.get('generation', 0) % stride) == 0

    def _flush_selection_trace(self):
        if not self.selection_trace_path or not self.selection_trace_buffer:
            return
        try:
            with open(self.selection_trace_path, "a", encoding="utf-8") as f:
                for record in self.selection_trace_buffer:
                    f.write(json.dumps(record, ensure_ascii=False))
                    f.write("\n")
            self.selection_trace_buffer = []
        except Exception:
            pass

    def _append_selection_trace(self, record):
        if not self.selection_trace_path:
            return
        if self.selection_trace_flush_interval <= 1:
            try:
                with open(self.selection_trace_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False))
                    f.write("\n")
            except Exception:
                pass
            return
        self.selection_trace_buffer.append(record)
        if len(self.selection_trace_buffer) >= self.selection_trace_flush_interval:
            self._flush_selection_trace()

    def _record_selection_trace(
        self,
        agent_pop: AgentPopulation,
        biased_objectives: List[List[float]],
        selected_indices: List[int],
        crowding: List[float],
        ranks: List[int]
    ):
        if not self._should_trace_selection():
            return

        pop_size = len(agent_pop.population)
        if pop_size == 0:
            return

        selected_set = set(selected_indices)
        selected_ranks = [ranks[i] for i in selected_indices] if selected_indices else [0]
        cutoff_rank = int(max(selected_ranks)) if selected_ranks else 0
        cutoff_candidates = [i for i in selected_indices if ranks[i] == cutoff_rank]
        cutoff_crowding = float(min([crowding[i] for i in cutoff_candidates])) if cutoff_candidates else 0.0

        def _obj_list(values):
            return [float(v) for v in np.atleast_1d(values).tolist()]

        def _entry(idx, reason):
            constraints = agent_pop.constraints[idx] if idx < len(agent_pop.constraints) else []
            violation = self._total_violation(constraints)
            return {
                "index": int(idx),
                "rank": int(ranks[idx]),
                "crowding": float(crowding[idx]),
                "violation": float(violation),
                "feasible": bool(violation <= 1e-10),
                "objectives": _obj_list(agent_pop.objectives[idx]),
                "biased_objectives": _obj_list(biased_objectives[idx]),
                "reason": reason
            }

        def _selected_reason(idx):
            rank = int(ranks[idx])
            crowd = float(crowding[idx])
            if rank < cutoff_rank:
                return "better_rank"
            if rank > cutoff_rank:
                return "selected_by_order"
            if crowd > cutoff_crowding:
                return "higher_crowding"
            if crowd < cutoff_crowding:
                return "selected_by_order"
            return "tie_break"

        def _eliminated_reason(idx):
            rank = int(ranks[idx])
            crowd = float(crowding[idx])
            if rank > cutoff_rank:
                return "worse_rank"
            if rank < cutoff_rank:
                return "eliminated_by_order"
            if crowd < cutoff_crowding:
                return "lower_crowding"
            if crowd > cutoff_crowding:
                return "eliminated_by_order"
            return "tie_break"

        def _limit_list(items):
            if self.selection_trace_limit is None:
                return items
            limit = int(self.selection_trace_limit)
            if limit <= 0:
                return []
            return items[:limit]

        mode = self.selection_trace_mode
        selected_entries = []
        eliminated_entries = []
        if mode != "stats":
            selected_entries = [_entry(i, _selected_reason(i)) for i in selected_indices]
            eliminated_entries = [_entry(i, _eliminated_reason(i)) for i in range(pop_size) if i not in selected_set]

        ranks_arr = np.asarray(ranks, dtype=int) if ranks else np.zeros(pop_size, dtype=int)
        if agent_pop.constraints and len(agent_pop.constraints) == pop_size:
            violations_arr = np.asarray([self._total_violation(c) for c in agent_pop.constraints], dtype=float)
        else:
            violations_arr = np.zeros(pop_size, dtype=float)

        selected_indices_arr = np.asarray(selected_indices, dtype=int)
        eliminated_indices_arr = np.asarray([i for i in range(pop_size) if i not in selected_set], dtype=int)

        def _rank_hist(indices):
            if indices.size == 0:
                return {}
            unique, counts = np.unique(ranks_arr[indices], return_counts=True)
            return {str(int(r)): int(c) for r, c in zip(unique, counts)}

        def _summary(indices):
            if indices.size == 0:
                return {
                    "feasible": 0,
                    "mean_violation": 0.0,
                    "rank_hist": {}
                }
            violations = violations_arr[indices]
            feasible = int(np.sum(violations <= 1e-10))
            mean_violation = float(np.mean(violations)) if violations.size > 0 else 0.0
            return {
                "feasible": feasible,
                "mean_violation": mean_violation,
                "rank_hist": _rank_hist(indices)
            }

        if mode == "summary":
            selected_entries = selected_entries[: min(10, len(selected_entries))]
            eliminated_entries = eliminated_entries[: min(10, len(eliminated_entries))]

        record = {
            "generation": int(self.history.get('generation', 0)),
            "role": agent_pop.role.value,
            "population_size": int(pop_size),
            "selected_count": int(len(selected_indices)),
            "eliminated_count": int(len(eliminated_indices_arr)),
            "cutoff": {
                "rank": cutoff_rank,
                "crowding": cutoff_crowding
            }
        }
        if mode == "stats":
            record["summary"] = {
                "selected": _summary(selected_indices_arr),
                "eliminated": _summary(eliminated_indices_arr)
            }
        else:
            record["selected"] = _limit_list(selected_entries)
            record["eliminated"] = _limit_list(eliminated_entries)
        self._append_selection_trace(record)

    # ---- BaseSolver abstract method adapters ----
    def _initialize(self) -> None:
        """å…¼å®¹ BaseSolverï¼šç¡®ä¿å¤šæ™ºèƒ½ä½“å†…éƒ¨å·²åˆå§‹åŒ–ã€?"""
        # BaseSolver __init__ 会先调用此方法，MultiAgent 的配置尚未就绪时先跳过
        if not isinstance(self.config, dict) or 'total_population' not in self.config:
            return
        if not hasattr(self, 'agent_populations') or not self.agent_populations:
            if not hasattr(self, 'agent_populations'):
                self.agent_populations = {}
            self._initialize_agents()
        if self.config.get('use_bias_system') and hasattr(self.problem, 'bias_manager'):
            self.problem.bias_manager.set_solver_instance(self)

    def _evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """å…¼å®¹ BaseSolverï¼šå¯¹ç»™å®šç§ç¾¤è¿›è¡ŒåŸºç¡€è¯„ä¼°ã€?"""
        objectives = []
        constraint_violations = []
        for individual in population:
            val = self.problem.evaluate(individual)
            obj = np.asarray(val, dtype=float).flatten()
            try:
                cons = self.problem.evaluate_constraints(individual)
                cons_arr = np.asarray(cons, dtype=float).flatten()
                violation = float(np.sum(np.maximum(cons_arr, 0.0))) if cons_arr.size > 0 else 0.0
            except Exception:
                violation = 0.0
            objectives.append(obj)
            constraint_violations.append(violation)
        return np.asarray(objectives, dtype=float), np.asarray(constraint_violations, dtype=float)

    def _evolve_generation(self) -> None:
        """å…¼å®¹ BaseSolverï¼šæ‰§è¡Œä¸€æ¬¡å¤šæ™ºèƒ½ä½“æ¼”åŒ–ã€?"""
        for pop in self.agent_populations.values():
            self.evaluate_population(pop)
        for pop in self.agent_populations.values():
            self.evolve_population(pop)

        gen = self.history.get('generation', 0)
        if gen % self.config.get('communication_interval', 1) == 0:
            self.communicate_between_agents()
        if gen % self.config.get('adaptation_interval', 1) == 0:
            self.adapt_agent_strategies(gen)
        self.history['generation'] = gen + 1

    def _initialize_agents(self):
        """初始化智能体种群"""
        total_pop = self.config['total_population']

        for role, ratio in self.config['agent_ratios'].items():
            pop_size = int(total_pop * ratio)

            # 根据角色设置偏置配置
            bias_profile = self._get_bias_profile(role)

            # 初始化种群
            pipeline = self._get_representation_pipeline(role)
            population = self._initialize_agent_population(pop_size, bias_profile, role, pipeline)

            self.agent_populations[role] = AgentPopulation(
                role=role,
                population=population,
                objectives=[],
                constraints=[],
                fitness=[],
                bias_profile=bias_profile,
                representation_pipeline=pipeline
            )

    def _get_bias_profile(self, role: AgentRole) -> Dict:
        """获取不同角色的偏置配置"""
        if role == AgentRole.EXPLORER:
            return {
                'diversity_weight': 2.0,        # 强调多样性
                'exploration_rate': 0.8,        # 高探索率
                'mutation_rate': 0.3,           # 高变异率
                'crossover_rate': 0.6,          # 较低交叉率
                'selection_pressure': 0.3,      # 低选择压力
                'constraint_tolerance': 0.5     # 高约束容忍度
            }
        elif role == AgentRole.EXPLOITER:
            return {
                'diversity_weight': 0.5,        # 弱化多样性
                'exploration_rate': 0.2,        # 低探索率
                'mutation_rate': 0.1,           # 低变异率
                'crossover_rate': 0.9,          # 高交叉率
                'selection_pressure': 0.8,      # 高选择压力
                'constraint_tolerance': 0.1     # 低约束容忍度
            }
        elif role == AgentRole.WAITER:
            return {
                'diversity_weight': 1.0,        # 中等多样性
                'exploration_rate': 0.1,        # 极低探索率
                'mutation_rate': 0.05,          # 极低变异率
                'crossover_rate': 0.7,          # 中等交叉率
                'selection_pressure': 0.5,      # 中等选择压力
                'constraint_tolerance': 0.3     # 中等约束容忍度
            }
        elif role == AgentRole.ADVISOR:
            # 建议者：智能分析与建议
            return {
                'diversity_weight': 1.2,        # 平衡多样性
                'exploration_rate': 0.5,        # 平衡探索
                'mutation_rate': 0.15,          # 低变异率（主要依靠建议）
                'crossover_rate': 0.7,          # 中等交叉率
                'selection_pressure': 0.5,      # 中等选择压力
                'constraint_tolerance': 0.3,    # 中等约束容忍度
                'analytical_weight': 0.8,       # 分析权重
                'advisory_influence': 0.7       # 建议影响权重
            }
        else:  # COORDINATOR
            return {
                'diversity_weight': 1.5,        # 较高多样性
                'exploration_rate': 0.4,        # 中等探索率
                'mutation_rate': 0.2,           # 中等变异率
                'crossover_rate': 0.8,          # 较高交叉率
                'selection_pressure': 0.6,      # 中等选择压力
                'constraint_tolerance': 0.4     # 中等约束容忍度
            }

    def _get_representation_pipeline(self, role: AgentRole):
        """Pick a role-specific representation pipeline if provided."""
        role_pipelines = self.config.get('representation_pipelines') or {}
        if isinstance(role_pipelines, dict):
            pipeline = role_pipelines.get(role)
            if pipeline is not None:
                return pipeline
        return self.config.get('representation_pipeline')

    def _initialize_agent_population(self, size: int, bias_profile: Dict, role: AgentRole, pipeline=None) -> List[np.ndarray]:
        """初始化智能体种群"""
        population = []
        bounds = self._get_effective_bounds(bias_profile)

        for i in range(size):
            if pipeline is not None and getattr(pipeline, 'initializer', None) is not None:
                context = {
                    'generation': 0,
                    'bounds': bounds,
                    'role': role.value
                }
                individual = pipeline.init(self.problem, context)
            else:
                if bias_profile['exploration_rate'] > 0.5:
                    # high exploration: uniform
                    individual = np.random.uniform(
                        low=bounds[:, 0],
                        high=bounds[:, 1],
                        size=self.dimension
                    )
                else:
                    # low exploration: center-focused
                    center = np.mean(bounds, axis=1)
                    radius = np.max(bounds[:, 1] - bounds[:, 0]) * 0.2
                    individual = center + np.random.randn(self.dimension) * radius
                    individual = np.clip(individual, bounds[:, 0], bounds[:, 1])

            population.append(individual)

        return population

    def evaluate_population(self, agent_pop: AgentPopulation):
        """评估种群（考虑角色偏置）"""
        agent_pop.objectives = []
        agent_pop.constraints = []
        agent_pop.fitness = []

        bias_module = getattr(self, 'bias_module', None)
        if bias_module is None:
            bias_module = getattr(self.problem, 'bias_module', None)

        for individual in agent_pop.population:
            # 基础评估
            val = self.problem.evaluate(individual)
            objectives = np.asarray(val, dtype=float).flatten().tolist()
            if hasattr(self.problem, 'evaluate_constraints'):
                cons = self.problem.evaluate_constraints(individual)
                constraints = np.asarray(cons, dtype=float).flatten().tolist()
            else:
                constraints = []

            context = {
                "problem": self.problem,
                "constraints": constraints.copy(),
                "constraint_violation": 0.0,
            }

            # 偏置模块（可选）：允许偏置提供约束信息
            if bias_module is not None:
                if len(objectives) == 1:
                    objectives = [bias_module.compute_bias(individual, float(objectives[0]), context=context)]
                else:
                    objectives = [
                        bias_module.compute_bias(individual, float(obj), context=context)
                        for obj in objectives
                    ]
                if not constraints and context.get("constraints"):
                    constraints = list(context["constraints"])

            # 计算约束违背度总和
            if constraints:
                total_violation = sum(abs(c) for c in constraints)
            else:
                total_violation = float(context.get("constraint_violation", 0.0))
                if total_violation > 0:
                    constraints = [total_violation]

            # 应用角色偏置
            biased_objectives = self._apply_role_bias(objectives, agent_pop.role)

            # 计算适应度（考虑约束）
            if total_violation > 0:
                fitness = -np.mean(biased_objectives) + total_violation * 1000  # 惩罚不可行解
            else:
                fitness = -np.mean(biased_objectives)

            agent_pop.objectives.append(objectives)
            agent_pop.constraints.append(constraints)
            agent_pop.fitness.append(fitness)

            # 更新最优个体
            if agent_pop.best_individual is None or \
               (total_violation == 0 and self._dominates(objectives, agent_pop.best_objectives)) or \
               (total_violation < sum(abs(c) for c in (agent_pop.best_constraints or []))):
                agent_pop.best_individual = individual.copy()
                agent_pop.best_objectives = objectives.copy()
                agent_pop.best_constraints = constraints.copy() if constraints else []

        self.stats['evaluations'] += len(agent_pop.population)

        # update role stats for scoring
        if agent_pop.constraints:
            violations = [self._total_violation(c) for c in agent_pop.constraints]
            feasible = sum(1 for v in violations if v == 0.0)
            agent_pop.feasible_rate = feasible / max(1, len(violations))
            agent_pop.avg_violation = float(np.mean(violations)) if violations else 0.0
        else:
            agent_pop.feasible_rate = 0.0
            agent_pop.avg_violation = 0.0

    def _apply_role_bias(self, objectives: List[float], role: AgentRole) -> List[float]:
        """应用角色偏置到目标值"""
        if role == AgentRole.EXPLORER:
            # 探索者：奖励新颖解，增加多样性
            diversity_bonus = np.random.randn() * 0.1 * np.std(objectives) if len(objectives) > 1 else 0
            return [obj + diversity_bonus for obj in objectives]
        elif role == AgentRole.EXPLOITER:
            # 开发者：优先考虑主要目标
            return [objectives[0]] + [obj * 0.7 for obj in objectives[1:]]
        elif role == AgentRole.WAITER:
            # 等待者：平衡所有目标
            return objectives
        elif role == AgentRole.ADVISOR:
            # 建议者：综合分析，考虑所有目标的平衡
            # 计算目标的加权平均值，更关注次要目标的改善
            if len(objectives) > 1:
                primary_weight = 0.6
                secondary_weight = 0.4 / (len(objectives) - 1)
                weighted_obj = objectives[0] * primary_weight + sum(objectives[1:]) * secondary_weight
                return [weighted_obj] + [obj * 0.9 for obj in objectives[1:]]
            return objectives
        else:  # COORDINATOR
            # 协调者：综合考虑
            return objectives

    def evolve_population(self, agent_pop: AgentPopulation):
        """
        进化种群 - 统一的 NSGA-II 框架 + 偏置系统

        核心理念：
        1. 所有角色使用统一的 NSGA-II 算法
        2. 通过偏置系统实现角色差异化
        3. 保持项目特色：NSGA-II + 偏置系统
        """
        pop_size = len(agent_pop.population)

        # ========== 第一步：应用角色偏置到适应度 ==========
        # 所有角色都用同样的评估，但应用不同的偏置
        biased_objectives = []
        for i, individual in enumerate(agent_pop.population):
            if i < len(agent_pop.objectives):
                # 应用角色偏置
                biased_obj = self._apply_role_bias(
                    agent_pop.objectives[i],
                    agent_pop.role
                )
                biased_objectives.append(biased_obj)

        # ========== 第二步：NSGA-II 选择（所有角色统一） ==========
        # 2.1 快速非支配排序
        self._crowding_distances = {}
        fronts = self._fast_non_dominated_sort(
            agent_pop.population,
            biased_objectives
        )

        # 2.2 计算拥挤距离
        for front in fronts:
            self._calculate_crowding_distance(front, biased_objectives)

        # 2.3 选择精英（基于 front rank 和 crowding distance）
        ranks = [0] * pop_size
        for front_idx, front in enumerate(fronts):
            for idx in front:
                if idx < pop_size:
                    ranks[idx] = front_idx
        crowding = [float(self._crowding_distances.get(i, 0.0)) for i in range(pop_size)]
        selected_indices = self._nsga2_select(
            fronts,
            pop_size
        )
        self._record_selection_trace(agent_pop, biased_objectives, selected_indices, crowding, ranks)

        # 精英个体直接进入下一代
        new_population = [
            agent_pop.population[i].copy()
            for i in selected_indices
        ]

        # ========== 第三步：遗传操作生成新个体 ==========
        # 生成剩余个体
        while len(new_population) < pop_size:
            # NSGA-II 锦标赛选择（基于偏置后的适应度）
            parent1_idx = self._nsga2_tournament_select(selected_indices, biased_objectives)
            parent2_idx = self._nsga2_tournament_select(selected_indices, biased_objectives)

            parent1 = agent_pop.population[parent1_idx]
            parent2 = agent_pop.population[parent2_idx]

            # 模拟二进制交叉（SBX）- NSGA-II 标准交叉算子
            child1, child2 = self._sbx_crossover(
                parent1,
                parent2,
                agent_pop.bias_profile
            )

            # 多项式变异 - NSGA-II 标准变异算子
            child1 = self._polynomial_mutation(child1, agent_pop.bias_profile)
            child2 = self._polynomial_mutation(child2, agent_pop.bias_profile)

            if agent_pop.representation_pipeline is not None and getattr(agent_pop.representation_pipeline, 'mutator', None) is not None:
                context = {
                    'generation': agent_pop.generation,
                    'bounds': self.var_bounds,
                    'role': agent_pop.role.value
                }
                child1 = agent_pop.representation_pipeline.mutate(child1, context)
                child2 = agent_pop.representation_pipeline.mutate(child2, context)

            new_population.append(child1)
            if len(new_population) < pop_size:
                new_population.append(child2)

        # 更新种群
        agent_pop.population = new_population[:pop_size]
        agent_pop.generation += 1

    def run(self):
        """运行多智能体优化"""
        print(f"[MultiAgent] 开始优化，最大代数: {self.config['max_generations']}")
        start_time = time.time()

        # 初始化偏置系统
        if self.config['use_bias_system'] and hasattr(self.problem, 'bias_manager'):
            self.problem.bias_manager.set_solver_instance(self)

        for generation in range(self.config['max_generations']):
            self.history['generation'] = generation

            # 评估所有种群
            for role, pop in self.agent_populations.items():
                self.evaluate_population(pop)

            # 进化所有种群
            for role, pop in self.agent_populations.items():
                self.evolve_population(pop)

            # 种群间交流
            if generation % self.config['communication_interval'] == 0:
                self.communicate_between_agents()
                print(f"[MultiAgent] Generation {generation}: 信息交流完成")

            # 动态调整策略
            if generation % self.config['adaptation_interval'] == 0:
                self.adapt_agent_strategies(generation)
                print(f"[MultiAgent] Generation {generation}: 策略调整完成")

            # 记录历史
            diversity = self.calculate_diversity()
            self.history['diversity'].append(diversity)

            # 记录全局最优
            if self.global_best_objectives is not None:
                self.history['best_objectives'].append(self.global_best_objectives.copy())

            # 记录各角色贡献
            for role, pop in self.agent_populations.items():
                if pop.best_objectives is not None:
                    self.history['agent_contributions'][role].append(np.mean(pop.best_objectives))

            # 进度报告
            if generation % 10 == 0:
                print(f"[MultiAgent] Generation {generation}:")
                print(f"  多样性: {diversity:.4f}")
                print(f"  评估次数: {self.stats['evaluations']}")
                if self.global_best_objectives:
                    print(f"  全局最优: {self.global_best_objectives}")
                for role, pop in self.agent_populations.items():
                    if pop.best_objectives:
                        total_violation = sum(abs(c) for c in (pop.best_constraints or []))
                        print(f"  {role.value}: {pop.best_objectives} (违规: {total_violation:.2f})")

            # advisor injection and waiter reassignment happen after logging
            self._apply_advisor_injection(generation)
            self._reassign_waiter_pool(generation)

        # 最终评估
        for role, pop in self.agent_populations.items():
            self.evaluate_population(pop)

        # 收集Pareto前沿
        pareto_front = self._extract_pareto_front()

        end_time = time.time()
        print(f"[MultiAgent] 优化完成！耗时: {end_time - start_time:.2f}秒")
        print(f"[MultiAgent] 总评估次数: {self.stats['evaluations']}")
        print(f"[MultiAgent] 找到 {len(pareto_front)} 个Pareto最优解")
        self._flush_selection_trace()

        return pareto_front

    def _extract_pareto_front(self) -> List[Dict]:
        """提取Pareto前沿"""
        all_individuals = []
        all_objectives = []
        all_constraints = []

        # 收集所有种群的个体
        for pop in self.agent_populations.values():
            for i, individual in enumerate(pop.population):
                if i < len(pop.objectives):
                    # 只保留可行解
                    total_violation = sum(abs(c) for c in (pop.constraints[i] if pop.constraints else []))
                    if total_violation == 0:
                        all_individuals.append(individual)
                        all_objectives.append(pop.objectives[i])
                        all_constraints.append(pop.constraints[i] if pop.constraints else [])

        # 提取非支配解
        pareto_front = []
        for i, obj in enumerate(all_objectives):
            dominated = False
            for j, other_obj in enumerate(all_objectives):
                if i != j and self._dominates(other_obj, obj):
                    dominated = True
                    break
            if not dominated:
                pareto_front.append({
                    'solution': all_individuals[i],
                    'objectives': all_objectives[i],
                    'constraints': all_constraints[i]
                })

        return pareto_front

    def get_population(self):
        """获取种群（兼容原始接口）"""
        all_pop = []
        for pop in self.agent_populations.values():
            all_pop.extend(pop.population)
        return all_pop

    def get_objectives(self):
        """获取目标值（兼容原始接口）"""
        all_objs = []
        for pop in self.agent_populations.values():
            all_objs.extend(pop.objectives)
        return all_objs

    def get_constraint_violations(self):
        """获取约束违背度（兼容原始接口）"""
        all_violations = []
        for pop in self.agent_populations.values():
            for constraints in pop.constraints:
                total_violation = sum(abs(c) for c in constraints) if constraints else 0
                all_violations.append(total_violation)
        return all_violations

    def environmental_selection(self, population, objectives, constraint_violations):
        """环境选择（兼容原始接口）"""
        # 在多智能体框架中，这个方法由各角色自行处理
        pass

    # 继承自BaseSolver的其他方法
    def solve(self, max_generations=None, **kwargs):
        """求解接口"""
        if max_generations:
            self.config['max_generations'] = max_generations

        return self.run()

    def get_results(self):
        """获取结果"""
        pareto_front = self._extract_pareto_front()
        return {
            'pareto_front': pareto_front,
            'history': self.history,
            'statistics': self.stats,
            'global_best': {
                'solution': self.global_best,
                'objectives': self.global_best_objectives,
                'constraints': self.global_best_constraints
            } if self.global_best is not None else None
        }
