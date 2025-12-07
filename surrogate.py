"""代理模型辅助优化 (Surrogate-Assisted Optimization)

核心思想：
- 用少量真实评估训练代理模型（GP/RBF/RF）
- 用代理模型快速预筛选大量候选解
- 选择最有希望的解进行真实评估
- 迭代更新代理模型

适用场景：
- 昂贵的仿真/实验评估（每次评估耗时长）
- 评估预算有限（总评估次数受限）
"""
import numpy as np
from typing import Optional, Literal
from base import BlackBoxProblem
from solver import BlackBoxSolverNSGAII


class SurrogateAssistedNSGAII(BlackBoxSolverNSGAII):
    """代理模型辅助的 NSGA-II

    策略：
    1. 初始阶段：用真实评估建立初始训练集
    2. 代理阶段：用代理模型评估大部分个体
    3. 更新阶段：选择最优/最不确定的个体进行真实评估
    4. 重训练：定期用新数据更新代理模型
    """

    def __init__(self, problem: BlackBoxProblem,
                 surrogate_type: Literal['gp', 'rbf', 'rf'] = 'gp'):
        super().__init__(problem)
        self.surrogate_type = surrogate_type

        # 代理模型相关参数
        self.real_eval_budget = 200  # 真实评估预算
        self.initial_samples = 50     # 初始真实评估数
        self.update_interval = 10     # 每隔多少代更新一次代理模型
        self.real_evals_per_gen = 5   # 每代真实评估个数

        # 数据存储
        self.X_real = []  # 真实评估的 X
        self.y_real = []  # 真实评估的目标值
        self.real_eval_count = 0

        # 代理模型
        self.surrogate = None
        self._init_surrogate()

    def _init_surrogate(self):
        """初始化代理模型"""
        if self.surrogate_type == 'gp':
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel
            kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
            self.surrogate = GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=5,
                alpha=1e-6,
                normalize_y=True
            )
        elif self.surrogate_type == 'rbf':
            from sklearn.kernel_approximation import RBFSampler
            from sklearn.linear_model import Ridge
            from sklearn.pipeline import Pipeline
            self.surrogate = Pipeline([
                ('rbf', RBFSampler(gamma=1.0, n_components=100)),
                ('ridge', Ridge(alpha=1.0))
            ])
        else:  # 'rf'
            from sklearn.ensemble import RandomForestRegressor
            self.surrogate = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

    def _evaluate_real(self, x):
        """真实评估"""
        obj = self.problem.evaluate(x)
        self.real_eval_count += 1
        self.X_real.append(x.copy())
        self.y_real.append(obj)
        return obj

    def _evaluate_surrogate(self, x):
        """代理模型评估"""
        if self.surrogate is None or len(self.X_real) < 5:
            return self._evaluate_real(x)

        x_2d = x.reshape(1, -1)
        
        if isinstance(self.surrogate, list):
            # 多目标，每个模型预测一个目标
            preds = []
            for model in self.surrogate:
                pred = model.predict(x_2d)
                preds.append(pred[0])
            return np.array(preds)
        
        pred = self.surrogate.predict(x_2d)

        # 多目标：返回向量；单目标：返回标量
        if self.num_objectives > 1:
            return pred[0]
        return float(pred[0])

    def _train_surrogate(self):
        """训练/更新代理模型"""
        if len(self.X_real) < 5:
            return

        X = np.array(self.X_real)
        y = np.array(self.y_real)

        # 多目标：每个目标训练一个模型
        if self.num_objectives > 1:
            if not isinstance(self.surrogate, list):
                self.surrogate = [self._init_single_surrogate()
                                 for _ in range(self.num_objectives)]
            for i, model in enumerate(self.surrogate):
                model.fit(X, y[:, i])
        else:
            self.surrogate.fit(X, y.ravel())

    def _init_single_surrogate(self):
        """为多目标创建单个代理模型"""
        if self.surrogate_type == 'gp':
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel
            kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
            return GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=5,
                alpha=1e-6,
                normalize_y=True
            )
        elif self.surrogate_type == 'rbf':
            from sklearn.kernel_approximation import RBFSampler
            from sklearn.linear_model import Ridge
            from sklearn.pipeline import Pipeline
            return Pipeline([
                ('rbf', RBFSampler(gamma=1.0, n_components=100)),
                ('ridge', Ridge(alpha=1.0))
            ])
        else:
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

    def _select_for_real_eval(self, population, objectives):
        """选择最有价值的个体进行真实评估

        策略：
        1. 非支配解优先
        2. 如果是 GP，选择预测不确定性最大的
        3. 否则选择目标值最优的
        """
        n_select = min(self.real_evals_per_gen,
                      self.real_eval_budget - self.real_eval_count)
        if n_select <= 0:
            return []

        # 找出非支配解
        pareto_indices = self._find_pareto_front_indices(objectives)

        if len(pareto_indices) >= n_select:
            # 从非支配解中随机选择
            return np.random.choice(pareto_indices, n_select, replace=False)

        # 不够的话，从剩余解中选择
        remaining = [i for i in range(len(population)) if i not in pareto_indices]
        n_more = n_select - len(pareto_indices)

        if self.surrogate_type == 'gp' and hasattr(self.surrogate, 'predict'):
            # GP：选择不确定性最大的
            X = np.array([population[i] for i in remaining])
            _, std = self.surrogate.predict(X, return_std=True)
            top_uncertain = np.argsort(std)[-n_more:]
            selected_remaining = [remaining[i] for i in top_uncertain]
        else:
            # 其他：随机选择
            selected_remaining = np.random.choice(remaining, n_more, replace=False)

        return list(pareto_indices) + list(selected_remaining)

    def _find_pareto_front_indices(self, objectives):
        """找出 Pareto 前沿的索引"""
        n = len(objectives)
        is_pareto = np.ones(n, dtype=bool)
        for i in range(n):
            for j in range(n):
                if i != j and self._dominates(objectives[j], objectives[i]):
                    is_pareto[i] = False
                    break
        return np.where(is_pareto)[0]

    def _dominates(self, obj1, obj2):
        """判断 obj1 是否支配 obj2（最小化）"""
        obj1 = np.atleast_1d(obj1)
        obj2 = np.atleast_1d(obj2)
        return np.all(obj1 <= obj2) and np.any(obj1 < obj2)

    def initialize_population(self):
        """初始化种群（使用真实评估）"""
        super().initialize_population()

        # 初始种群全部真实评估
        n_init = min(self.initial_samples, len(self.population))
        for i in range(n_init):
            obj = self._evaluate_real(self.population[i])
            self.objectives[i] = obj

        # 训练初始代理模型
        self._train_surrogate()

        if self.enable_progress_log:
            print(f"[Surrogate] 初始化完成，真实评估: {self.real_eval_count}/{self.real_eval_budget}")

    def evolve_one_generation(self):
        """进化一代（使用代理模型）"""
        if self.real_eval_count >= self.real_eval_budget:
            # 预算用完，停止
            self.running = False
            return

        # 1. 选择
        parents = self.selection()
        
        # 2. 交叉
        offspring = self.crossover(parents)
        
        # 3. 变异
        offspring = self.mutate(offspring)

        # 4. 代理模型评估
        offspring_objs = []
        for i in range(len(offspring)):
            obj = self._evaluate_surrogate(offspring[i])
            offspring_objs.append(obj)
        
        # 转换为 numpy 数组
        offspring_objs = np.array(offspring_objs)
        if offspring_objs.ndim == 1:
             offspring_objs = offspring_objs.reshape(-1, 1)

        # 5. 选择部分个体进行真实评估
        selected_indices = self._select_for_real_eval(offspring, offspring_objs)
        for idx in selected_indices:
            real_obj = self._evaluate_real(offspring[idx])
            offspring_objs[idx] = real_obj

        # 6. 合并父代和子代
        combined_pop = np.vstack([self.population, offspring])
        combined_objs = np.vstack([self.objectives, offspring_objs])

        # 7. 环境选择
        if self.constraint_violations is None:
             self.constraint_violations = np.zeros(len(self.population))
        
        offspring_violations = np.zeros(len(offspring))
        combined_violations = np.concatenate([self.constraint_violations, offspring_violations])

        self.environmental_selection(combined_pop, combined_objs, combined_violations)

        # 定期更新代理模型
        if self.generation % self.update_interval == 0:
            self._train_surrogate()
            if self.enable_progress_log:
                print(f"[Surrogate] 第 {self.generation} 代，真实评估: {self.real_eval_count}/{self.real_eval_budget}")

        self.generation += 1

    def run(self, plot=False):
        """运行优化（重写以支持代理模型）"""
        self.running = True
        self.initialize_population()
        self.update_pareto_solutions()

        while self.running and self.generation < self.max_generations:
            if self.real_eval_count >= self.real_eval_budget:
                break
            self.evolve_one_generation()
            self.update_pareto_solutions()

        if self.enable_progress_log:
            print(f"[Surrogate] 优化完成！真实评估: {self.real_eval_count}/{self.real_eval_budget}")
            print(f"[Surrogate] 找到 {len(self.pareto_solutions)} 个 Pareto 解")

        return {
            'pareto_solutions': self.pareto_solutions,
            'pareto_objectives': self.pareto_objectives,
            'real_eval_count': self.real_eval_count,
            'generation': self.generation
        }


def run_surrogate_assisted(problem: BlackBoxProblem,
                          surrogate_type: Literal['gp', 'rbf', 'rf'] = 'gp',
                          real_eval_budget: int = 200,
                          initial_samples: int = 50,
                          pop_size: int = 80,
                          max_generations: int = 150) -> dict:
    """便捷函数：运行代理模型辅助优化

    参数：
        problem: 黑箱问题
        surrogate_type: 代理模型类型 ('gp', 'rbf', 'rf')
        real_eval_budget: 真实评估预算
        initial_samples: 初始真实评估数
        pop_size: 种群大小
        max_generations: 最大代数

    返回：
        结果字典，包含 pareto_solutions, real_eval_count 等
    """
    solver = SurrogateAssistedNSGAII(problem, surrogate_type=surrogate_type)
    solver.real_eval_budget = real_eval_budget
    solver.initial_samples = initial_samples
    solver.pop_size = pop_size
    solver.max_generations = max_generations

    return solver.run()
