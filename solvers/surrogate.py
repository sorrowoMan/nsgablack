"""代理模型辅助优化 (Surrogate-Assisted Optimization)

核心思想：
- 用少量真实评估训练代理模型（GP/RBF/RF）
- 用代理模型快速预筛选大量候选解
- 选择最有希望的解进行真实评估
- 迭代更新代理模型

适用场景：
- 昂贵的仿真/实验评估（每次评估耗时长）
- 评估预算有限（总评估次数受限）

新增功能：
- 模型保存/加载：避免重复训练
- 质量监控：自动检测模型退化并重训练
- 在线学习：增量更新模型
- 多模型集成：GP+RF+RBF加权平均提高鲁棒性
"""
import numpy as np
import os
import joblib
from typing import Optional, Literal, List, Dict, Any
from sklearn.model_selection import cross_val_score
from sklearn.metrics import r2_score, mean_squared_error
try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from core.base import BlackBoxProblem


class EnsembleSurrogate:
    """多模型集成代理模型

    组合 GP、RF、RBF 三种模型，使用加权平均预测
    """

    def __init__(self, models: List[Any], weights: Optional[List[float]] = None):
        self.models = models
        self.weights = weights if weights else [1.0 / len(models)] * len(models)
        self.performance_history = []

    def fit(self, X, y):
        """训练所有子模型"""
        for model in self.models:
            model.fit(X, y)

    def predict(self, X):
        """加权平均预测"""
        predictions = []
        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)
        weighted_pred = np.average(predictions, axis=0, weights=self.weights)
        return weighted_pred

    def update_weights(self, X_val, y_val):
        """根据验证集性能更新权重"""
        if len(X_val) < 3:
            return

        errors = []
        for model in self.models:
            try:
                pred = model.predict(X_val)
                error = mean_squared_error(y_val, pred)
                errors.append(error)
            except Exception:
                errors.append(float('inf'))

        # 转换为权重（误差越小权重越大）
        errors = np.array(errors)
        if np.all(np.isinf(errors)):
            self.weights = [1.0 / len(self.models)] * len(self.models)
        else:
            inv_errors = 1.0 / (errors + 1e-10)
            self.weights = inv_errors / np.sum(inv_errors)


try:
    # 当作为包导入时使用相对导入
    from .nsga2 import BlackBoxSolverNSGAII
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from solvers.nsga2 import BlackBoxSolverNSGAII

class SurrogateAssistedNSGAII(BlackBoxSolverNSGAII):
    """代理模型辅助的 NSGA-II

    策略：
    1. 初始阶段：用真实评估建立初始训练集
    2. 代理阶段：用代理模型评估大部分个体
    3. 更新阶段：选择最优/最不确定的个体进行真实评估
    4. 重训练：定期用新数据更新代理模型
    """

    def __init__(self, problem: BlackBoxProblem,
                 surrogate_type: Literal['gp', 'rbf', 'rf', 'ensemble'] = 'gp'):
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
        self.last_train_index = 0  # 在线学习：上次训练的数据索引

        # 代理模型
        self.surrogate = None
        self._init_surrogate()

        # 质量监控
        self.model_metrics = []  # 记录每次训练的质量指标
        self.quality_threshold = 0.5  # R²阈值，低于此值触发重训练
        self.enable_quality_check = True

    def _init_surrogate(self):
        """初始化代理模型"""
        if self.surrogate_type == 'ensemble':
            # 创建集成模型
            models = [
                self._create_gp_model(),
                self._create_rf_model(),
                self._create_rbf_model()
            ]
            self.surrogate = EnsembleSurrogate(models)
        elif self.surrogate_type == 'gp':
            self.surrogate = self._create_gp_model()
        elif self.surrogate_type == 'rbf':
            self.surrogate = self._create_rbf_model()
        else:  # 'rf'
            self.surrogate = self._create_rf_model()

    def _create_gp_model(self):
        """创建高斯过程模型"""
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
        return GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=5,
            alpha=1e-6,
            normalize_y=True
        )

    def _create_rbf_model(self):
        """创建RBF模型"""
        from sklearn.kernel_approximation import RBFSampler
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import Pipeline
        return Pipeline([
            ('rbf', RBFSampler(gamma=1.0, n_components=100)),
            ('ridge', Ridge(alpha=1.0))
        ])

    def _create_rf_model(self):
        """创建随机森林模型"""
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

    def _evaluate_real(self, x, individual_id=None):
        """真实评估"""
        obj = self.problem.evaluate(x)

        # 应用 bias 模块
        if self.enable_bias and self.bias_module is not None:
            obj_arr = np.atleast_1d(obj)
            if self.num_objectives == 1:
                obj = self.bias_module.compute_bias(x, float(obj_arr[0]), individual_id)
            else:
                obj_biased = []
                for i in range(len(obj_arr)):
                    f_biased = self.bias_module.compute_bias(x, float(obj_arr[i]), individual_id)
                    obj_biased.append(f_biased)
                obj = np.array(obj_biased)

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

    def _train_surrogate(self, incremental: bool = False):
        """训练/更新代理模型

        参数：
            incremental: 是否使用增量学习（仅用新数据）
        """
        if len(self.X_real) < 5:
            return

        X = np.array(self.X_real)
        y = np.array(self.y_real)

        # 在线学习：只使用新数据
        if incremental and self.last_train_index < len(self.X_real):
            X_new = X[self.last_train_index:]
            y_new = y[self.last_train_index:]
            if len(X_new) < 3:  # 新数据太少，跳过
                return
            X_train, y_train = X_new, y_new
        else:
            X_train, y_train = X, y

        # 多目标：每个目标训练一个模型
        if self.num_objectives > 1:
            if not isinstance(self.surrogate, list):
                self.surrogate = [self._init_single_surrogate()
                                 for _ in range(self.num_objectives)]
            for i, model in enumerate(self.surrogate):
                if incremental and hasattr(model, 'partial_fit'):
                    model.partial_fit(X_train, y_train[:, i])
                else:
                    model.fit(X, y[:, i])
        else:
            if incremental and hasattr(self.surrogate, 'partial_fit'):
                self.surrogate.partial_fit(X_train, y_train.ravel())
            else:
                self.surrogate.fit(X, y.ravel())

        # 更新训练索引
        self.last_train_index = len(self.X_real)

        # 计算并记录模型质量
        metrics = self._compute_model_quality(X, y)
        metrics['generation'] = self.generation
        metrics['n_samples'] = len(X)
        self.model_metrics.append(metrics)

        if self.enable_progress_log and len(self.model_metrics) % 5 == 0:
            print(f"[Surrogate] Model quality - R2: {metrics['r2']:.3f}, RMSE: {metrics['rmse']:.3f}")

    def _init_single_surrogate(self):
        """为多目标创建单个代理模型"""
        if self.surrogate_type == 'ensemble':
            models = [
                self._create_gp_model(),
                self._create_rf_model(),
                self._create_rbf_model()
            ]
            return EnsembleSurrogate(models)
        elif self.surrogate_type == 'gp':
            return self._create_gp_model()
        elif self.surrogate_type == 'rbf':
            return self._create_rbf_model()
        else:
            return self._create_rf_model()

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
            obj = self._evaluate_real(self.population[i], individual_id=i)
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
            real_obj = self._evaluate_real(offspring[idx], individual_id=idx)
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

    def save_surrogate(self, path: str):
        """保存代理模型到文件

        参数：
            path: 保存路径（.pkl 或 .joblib）
        """
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        data = {
            'surrogate': self.surrogate,
            'surrogate_type': self.surrogate_type,
            'X_real': self.X_real,
            'y_real': self.y_real,
            'real_eval_count': self.real_eval_count,
            'last_train_index': self.last_train_index,
            'model_metrics': self.model_metrics,
            'num_objectives': self.num_objectives,
            'dimension': self.dimension
        }
        joblib.dump(data, path)
        if self.enable_progress_log:
            print(f"[Surrogate] 模型已保存到: {path}")

    def load_surrogate(self, path: str):
        """从文件加载代理模型

        参数：
            path: 模型文件路径
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"模型文件不存在: {path}")

        data = joblib.load(path)
        self.surrogate = data['surrogate']
        self.surrogate_type = data['surrogate_type']
        self.X_real = data['X_real']
        self.y_real = data['y_real']
        self.real_eval_count = data['real_eval_count']
        self.last_train_index = data.get('last_train_index', len(self.X_real))
        self.model_metrics = data.get('model_metrics', [])

        if self.enable_progress_log:
            print(f"[Surrogate] 模型已加载，包含 {len(self.X_real)} 个训练样本")

    def _compute_model_quality(self, X, y) -> Dict[str, float]:
        """计算模型质量指标

        返回：
            包含 r2 和 rmse 的字典
        """
        if len(X) < 10:
            return {'r2': 0.0, 'rmse': float('inf')}

        try:
            if self.num_objectives > 1:
                # 多目标：计算每个目标的平均质量
                r2_scores = []
                rmse_scores = []
                for i, model in enumerate(self.surrogate):
                    cv_scores = cross_val_score(model, X, y[:, i], cv=min(5, len(X)//2),
                                                scoring='r2', n_jobs=1)
                    r2_scores.append(np.mean(cv_scores))
                    y_pred = model.predict(X)
                    rmse_scores.append(np.sqrt(mean_squared_error(y[:, i], y_pred)))
                return {'r2': np.mean(r2_scores), 'rmse': np.mean(rmse_scores)}
            else:
                # 单目标
                cv_scores = cross_val_score(self.surrogate, X, y.ravel(),
                                          cv=min(5, len(X)//2), scoring='r2', n_jobs=1)
                y_pred = self.surrogate.predict(X)
                rmse = np.sqrt(mean_squared_error(y.ravel(), y_pred))
                return {'r2': np.mean(cv_scores), 'rmse': rmse}
        except Exception:
            return {'r2': 0.0, 'rmse': float('inf')}

    def _check_model_quality(self) -> bool:
        """检查模型质量，返回是否需要重训练"""
        if not self.enable_quality_check or len(self.model_metrics) == 0:
            return False

        latest_metric = self.model_metrics[-1]
        if latest_metric['r2'] < self.quality_threshold:
            if self.enable_progress_log:
                print(f"[Surrogate] 模型质量下降 (R²={latest_metric['r2']:.3f})，触发重训练")
            return True
        return False

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
                          surrogate_type: Literal['gp', 'rbf', 'rf', 'ensemble'] = 'gp',
                          real_eval_budget: int = 200,
                          initial_samples: int = 50,
                          pop_size: int = 80,
                          max_generations: int = 150) -> dict:
    """便捷函数：运行代理模型辅助优化

    参数：
        problem: 黑箱问题
        surrogate_type: 代理模型类型 ('gp', 'rbf', 'rf', 'ensemble')
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
