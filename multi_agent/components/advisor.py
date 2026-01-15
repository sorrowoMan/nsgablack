"""Auto-extracted mixin module."""
from __future__ import annotations


import random
from typing import List, Dict, Optional
import numpy as np
from ..core.role import AgentRole
from ..core.population import AgentPopulation
try:
    from ...bias.core.base import OptimizationContext
except Exception:
    try:
        from bias.core.base import OptimizationContext
    except Exception:
        OptimizationContext = None

class AdvisorMixin:
    """Mixin for multi-agent solver."""

    def _generate_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """
        建议者：基于分析和建议生成新解

        实现三种建议方法：
        1. 基于种群统计分析（基础版）
        2. 基于贝叶斯优化（高级版，需要安装gpy）
        3. 基于机器学习（高级版，需要安装sklearn）
        """
        advisory_method = self.config.get('advisory_method', 'statistical')

        if advisory_method == 'bayesian':
            return self._generate_bayesian_advisory_solution(advisor_pop)
        elif advisory_method == 'ml':
            return self._generate_ml_advisory_solution(advisor_pop)
        else:
            return self._generate_statistical_advisory_solution(advisor_pop)

    def _generate_statistical_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于统计分析的建议（无需额外依赖）"""
        # 收集所有种群的非支配解
        all_solutions = []
        all_objectives = []

        for role, pop in self.agent_populations.items():
            for i, individual in enumerate(pop.population):
                if i < len(pop.objectives):
                    all_solutions.append(individual)
                    all_objectives.append(pop.objectives[i])

        if not all_solutions:
            return self._initialize_agent_population(1, advisor_pop.bias_profile, advisor_pop.role)[0]

        all_solutions = np.array(all_solutions)
        all_objectives = np.array(all_objectives)

        # 分析解的分布特征
        mean_solution = np.mean(all_solutions, axis=0)
        std_solution = np.std(all_solutions, axis=0)

        # 识别有希望的区域（目标值较好的解）
        if len(all_objectives) > 0:
            # 使用加权和来确定"好"的解
            if all_objectives[0] is not None and len(all_objectives[0]) > 0:
                objective_means = np.mean(all_objectives, axis=0)
                # 找到综合目标较好的解
                weighted_scores = []
                for obj in all_objectives:
                    if obj is not None:
                        score = -np.mean(obj)  # 负号因为我们要最小化
                        weighted_scores.append(score)
                    else:
                        weighted_scores.append(0)

                weighted_scores = np.array(weighted_scores)

                # 选择前20%的解
                top_indices = np.argsort(weighted_scores)[-max(1, len(all_solutions) // 5):]
                promising_solutions = all_solutions[top_indices]

                if len(promising_solutions) > 0:
                    # 在有希望的区域生成新解
                    center = np.mean(promising_solutions, axis=0)
                    # 小幅扰动，保持在该区域
                    child = center + np.random.randn(len(center)) * std_solution * 0.3
                else:
                    child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5
            else:
                child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5
        else:
            child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5

        bounds = self._get_effective_bounds(advisor_pop.bias_profile)
        return self._clip_to_bounds(child, bounds)

    def _generate_bayesian_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于贝叶斯优化的建议（需要gpy库）"""
        try:
            from scipy.optimize import minimize
            from scipy.stats import norm

            # 收集训练数据
            X_train = []
            y_train = []

            for role, pop in self.agent_populations.items():
                for i, individual in enumerate(pop.population):
                    if i < len(pop.objectives) and pop.objectives[i] is not None:
                        X_train.append(individual)
                        # 使用目标值的加权和
                        y_train.append(-np.mean(pop.objectives[i]))  # 负号因为我们要最小化

            if len(X_train) < 5:  # 数据不足，回退到统计方法
                return self._generate_statistical_advisory_solution(advisor_pop)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            # 简化的采集函数：使用距离加权的方法
            def acquisition_function(x):
                # 计算与已知解的距离
                distances = np.linalg.norm(X_train - x, axis=1)
                # 加权：距离近的解权重高
                weights = np.exp(-distances / distances.mean())
                # 预测值（加权平均）
                predicted = np.sum(weights * y_train) / np.sum(weights)
                # 探索项（鼓励探索未知区域）
                exploration = distances.min() * 0.1
                return predicted + exploration

            # 找到最优解附近的有希望区域
            best_idx = np.argmin(y_train)
            best_solution = X_train[best_idx]

            # 在最优解附近搜索
            result = minimize(
                lambda x: -acquisition_function(x),
                x0=best_solution,
                bounds=[(self.var_bounds[i, 0], self.var_bounds[i, 1]) for i in range(len(best_solution))],
                method='L-BFGS-B'
            )

            if result.success:
                child = result.x
            else:
                child = best_solution + np.random.randn(len(best_solution)) * 0.1

        except ImportError:
            # 没有scipy，回退到统计方法
            return self._generate_statistical_advisory_solution(advisor_pop)
        except Exception as e:
            # 出错，回退到统计方法
            print(f"[Advisor] 贝叶斯建议出错: {e}，使用统计方法")
            return self._generate_statistical_advisory_solution(advisor_pop)

        bounds = self._get_effective_bounds(advisor_pop.bias_profile)
        return self._clip_to_bounds(child, bounds)

    def _generate_ml_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于机器学习的建议（需要sklearn库）"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from scipy.stats import norm

            # 收集训练数据
            X_train = []
            y_train = []

            for role, pop in self.agent_populations.items():
                for i, individual in enumerate(pop.population):
                    if i < len(pop.objectives) and pop.objectives[i] is not None:
                        X_train.append(individual)
                        y_train.append(-np.mean(pop.objectives[i]))  # 负号因为我们要最小化

            if len(X_train) < 10:  # 数据不足，回退到统计方法
                return self._generate_statistical_advisory_solution(advisor_pop)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            # 训练随机森林模型
            model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
            model.fit(X_train, y_train)

            # 预测当前所有解的目标值
            predictions = model.predict(X_train)

            # 找到预测最好的解
            best_idx = np.argmin(predictions)
            best_solution = X_train[best_idx]

            # 在最优解附近生成新解，结合模型的不确定性
            # 使用随机森林的树方差作为不确定性估计
            tree_predictions = []
            for tree in model.estimators_:
                tree_predictions.append(tree.predict([best_solution])[0])

            uncertainty = np.std(tree_predictions)

            # 在最优解附近探索，步长与不确定性相关
            child = best_solution + np.random.randn(len(best_solution)) * uncertainty * 0.5

        except ImportError:
            # 没有sklearn，回退到统计方法
            return self._generate_statistical_advisory_solution(advisor_pop)
        except Exception as e:
            # 出错，回退到统计方法
            print(f"[Advisor] ML建议出错: {e}，使用统计方法")
            return self._generate_statistical_advisory_solution(advisor_pop)

        bounds = self._get_effective_bounds(advisor_pop.bias_profile)
        return self._clip_to_bounds(child, bounds)

    def _apply_advisor_injection(self, generation: int) -> None:
        """Generate advisor candidates and inject into target roles."""
        interval = int(self.config.get('advisor_injection_interval', 1))
        if interval <= 0 or generation % interval != 0:
            return

        per_role = int(self.config.get('advisor_injection_k', 0))
        if per_role <= 0:
            return

        pool_size = int(self.config.get('advisor_candidate_pool', 1))
        pool_size = max(1, pool_size)

        advisor_pop = self.agent_populations.get(AgentRole.ADVISOR)
        if advisor_pop is None or not advisor_pop.population:
            return

        targets = self._resolve_role_list(
            self.config.get('advisor_injection_roles'),
            default=[AgentRole.EXPLORER, AgentRole.EXPLOITER]
        )
        jitter = float(self.config.get('advisor_injection_jitter', 0.0))

        for role in targets:
            pop = self.agent_populations.get(role)
            if pop is None or not pop.population:
                continue
            candidates = []
            for _ in range(per_role):
                cand = self._select_advisor_candidate(
                    advisor_pop,
                    pop,
                    generation,
                    pool_size
                )
                if jitter > 0:
                    cand = cand + np.random.randn(len(cand)) * jitter
                bounds = self._get_effective_bounds(pop.bias_profile)
                cand = self._clip_to_bounds(cand, bounds)
                candidates.append(cand)
            self._inject_archive_candidates(pop, candidates)

    def _get_advisor_candidate_sources(self):
        sources = self.config.get('advisor_candidate_sources')
        weights = {}
        if isinstance(sources, dict):
            weights = {str(k).lower(): float(v) for k, v in sources.items() if v is not None}
            sources = list(weights.keys())
        elif sources is None:
            return None, {}
        elif isinstance(sources, str):
            sources = [sources]
        else:
            sources = list(sources)

        normalized = []
        for item in sources:
            if not item:
                continue
            key = str(item).strip().lower()
            if key and key not in normalized:
                normalized.append(key)
        sources = normalized

        extra_weights = self.config.get('advisor_candidate_source_weights') or {}
        for key, value in extra_weights.items():
            if value is None:
                continue
            weights.setdefault(str(key).lower(), float(value))
        return sources, weights

    def _choose_weighted_source(self, sources: List[str], weights: Dict[str, float]) -> Optional[str]:
        if not sources:
            return None
        if not weights:
            return random.choice(sources)
        weight_list = [max(0.0, float(weights.get(s, 1.0))) for s in sources]
        if sum(weight_list) <= 0:
            return random.choice(sources)
        return random.choices(sources, weights=weight_list, k=1)[0]

    def _build_advisor_source_schedule(
        self,
        sources: List[str],
        weights: Dict[str, float],
        pool_size: int
    ) -> List[str]:
        if not sources or pool_size <= 0:
            return []
        schedule = []
        if pool_size >= len(sources):
            schedule.extend(sources)
            remaining = pool_size - len(sources)
        else:
            remaining = pool_size
        for _ in range(remaining):
            choice = self._choose_weighted_source(sources, weights)
            if choice:
                schedule.append(choice)
        return schedule

    def _generate_random_candidate(self, target_pop: AgentPopulation) -> Optional[np.ndarray]:
        if target_pop is None:
            return None
        candidates = self._initialize_agent_population(1, target_pop.bias_profile, target_pop.role)
        if candidates:
            return candidates[0]
        return None

    def _generate_advisor_candidate_from_source(
        self,
        source: str,
        advisor_pop: AgentPopulation,
        target_pop: AgentPopulation,
        generation: int
    ) -> Optional[np.ndarray]:
        if not source:
            return None
        source = source.strip().lower()
        if source in ('archive', 'archives'):
            candidates = self._select_archive_candidates(target_pop.role, 1)
            if candidates:
                return candidates[0]
            return self._generate_random_candidate(target_pop)
        if source in ('random', 'sample', 'sampling'):
            return self._generate_random_candidate(target_pop)
        if source in ('bayesian', 'bayes'):
            return self._generate_bayesian_advisory_solution(advisor_pop)
        if source in ('ml', 'model'):
            return self._generate_ml_advisory_solution(advisor_pop)
        if source in ('statistical', 'stats'):
            return self._generate_statistical_advisory_solution(advisor_pop)
        if source in ('advisory', 'auto'):
            return self._generate_advisory_solution(advisor_pop)
        return self._generate_advisory_solution(advisor_pop)

    def _select_advisor_candidate(
        self,
        advisor_pop: AgentPopulation,
        target_pop: AgentPopulation,
        generation: int,
        pool_size: int
    ) -> np.ndarray:
        """Pick the best candidate from a small advisory pool."""
        best_candidate = None
        best_score = None
        sources, weights = self._get_advisor_candidate_sources()
        schedule = []
        if sources:
            schedule = self._build_advisor_source_schedule(sources, weights, pool_size)

        if schedule:
            for source in schedule:
                cand = self._generate_advisor_candidate_from_source(
                    source,
                    advisor_pop,
                    target_pop,
                    generation
                )
                if cand is None:
                    continue
                score = self._score_advisor_candidate(
                    cand,
                    advisor_pop,
                    target_pop,
                    generation
                )
                if best_score is None or score > best_score:
                    best_score = score
                    best_candidate = cand
        else:
            for _ in range(pool_size):
                cand = self._generate_advisory_solution(advisor_pop)
                score = self._score_advisor_candidate(
                    cand,
                    advisor_pop,
                    target_pop,
                    generation
                )
                if best_score is None or score > best_score:
                    best_score = score
                    best_candidate = cand

        if best_candidate is None:
            best_candidate = self._generate_advisory_solution(advisor_pop)
        return best_candidate

    def _build_advisor_bias_context(
        self,
        x: np.ndarray,
        advisor_pop: AgentPopulation,
        target_pop: AgentPopulation,
        generation: int,
        constraints: List[float],
        violation: float,
        objectives: Optional[List[float]]
    ):
        if OptimizationContext is None:
            return None
        try:
            metrics = {'constraint_violation': float(violation)}
            if objectives is not None:
                metrics['objectives'] = objectives
            metrics['target_role'] = target_pop.role.value
            problem_data = {
                'role': AgentRole.ADVISOR.value,
                'target_role': target_pop.role.value,
                'archives': self.archives,
                'target_population': target_pop.population,
                'global_best': self.global_best,
                'global_best_objectives': self.global_best_objectives,
                'constraints': constraints,
                'constraint_violation': violation,
                'objectives': objectives,
                'problem': self.problem,
            }
            context = OptimizationContext(
                generation=generation,
                individual=x,
                population=advisor_pop.population,
                metrics=metrics,
                history=self.history.get('best_objectives', []),
                problem_data=problem_data
            )
            context.role = AgentRole.ADVISOR.value
            context.target_role = target_pop.role.value
            context.archives = self.archives
            context.target_population = target_pop.population
            context.global_best = self.global_best
            context.global_best_objectives = self.global_best_objectives
            context.constraints = constraints
            context.constraint_violation = violation
            context.objectives = objectives
            context.problem = self.problem
            return context
        except Exception:
            return None

    def _score_advisor_candidate(
        self,
        x: np.ndarray,
        advisor_pop: AgentPopulation,
        target_pop: AgentPopulation,
        generation: int
    ) -> float:
        biases = self.config.get('advisor_score_biases') or []
        use_constraints = bool(self.config.get('advisor_score_use_constraints', True))
        use_objectives = bool(self.config.get('advisor_score_use_objectives', False))

        constraints = []
        violation = 0.0
        objectives = None

        if use_constraints and hasattr(self.problem, 'evaluate_constraints'):
            try:
                cons = self.problem.evaluate_constraints(x)
                constraints = np.asarray(cons, dtype=float).flatten().tolist()
                violation = self._total_violation(constraints)
            except Exception:
                constraints = []
                violation = 0.0

        if use_objectives:
            try:
                val = self.problem.evaluate(x)
                objectives = np.asarray(val, dtype=float).flatten().tolist()
            except Exception:
                objectives = None

        context = {
            'role': AgentRole.ADVISOR.value,
            'target_role': target_pop.role.value,
            'generation': generation,
            'archives': self.archives,
            'population': advisor_pop.population,
            'target_population': target_pop.population,
            'global_best': self.global_best,
            'global_best_objectives': self.global_best_objectives,
            'constraints': constraints,
            'constraint_violation': violation,
            'objectives': objectives,
            'problem': self.problem,
        }
        opt_context = self._build_advisor_bias_context(
            x,
            advisor_pop,
            target_pop,
            generation,
            constraints,
            violation,
            objectives
        )

        score = 0.0
        if use_constraints and violation > 0:
            score -= float(violation)
        if use_objectives and objectives:
            score -= float(np.mean(objectives))

        for bias in biases:
            score += self._evaluate_advisor_bias(bias, x, constraints, context, opt_context)

        return float(score)

    def _evaluate_advisor_bias(self, bias, x, constraints, context, opt_context=None) -> float:
        if opt_context is not None:
            for handler in ('compute_with_tracking', 'compute'):
                if hasattr(bias, handler):
                    func = getattr(bias, handler)
                    for args in (
                        (x, opt_context),
                        (opt_context,),
                        (x,),
                    ):
                        try:
                            return self._extract_score_value(func(*args))
                        except Exception:
                            continue

        if hasattr(bias, 'compute_bias'):
            try:
                value = bias.compute_bias(x, 0.0, context=context)
                return -float(value)
            except Exception:
                pass

        for handler in ('compute_score', 'score', 'compute'):
            if hasattr(bias, handler):
                func = getattr(bias, handler)
                for args in (
                    (x, constraints, context),
                    (x, context),
                    (x, constraints),
                    (x,),
                    (context,),
                ):
                    try:
                        return self._extract_score_value(func(*args))
                    except Exception:
                        continue

        if callable(bias):
            for args in (
                (x, constraints, context),
                (x, context),
                (x, constraints),
                (x,),
                (context,),
            ):
                try:
                    return self._extract_score_value(bias(*args))
                except Exception:
                    continue

        return 0.0

