"""
代理模型训练器

整合真实评估函数、数据收集和模型训练的核心组件。
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import json
import os
import numpy as np
from abc import ABC, abstractmethod
from ..core.base import BlackBoxProblem
from .base import BaseSurrogateModel
from .manager import SurrogateManager
from .features import FeatureExtractor
from .strategies import SurrogateStrategy
from .utils import get_num_objectives, get_problem_bounds


class TrueEvaluator(ABC):
    """真实评估函数抽象基类"""

    @abstractmethod
    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """
        真实评估函数（通常是昂贵的）

        Args:
            x: 解向量

        Returns:
            目标值
        """
        pass


class ProductionEvaluator(TrueEvaluator):
    """生产调度问题的真实评估函数"""

    def __init__(self, problem_data):
        """
        初始化生产调度评估器

        Args:
            problem_data: 问题数据（需求、供应、机器等）
        """
        self.problem_data = problem_data
        self.evaluation_count = 0

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """
        真实的生产调度评估

        这里调用实际的优化算法，如：
        - NSGA-II求解器
        - 生产调度模拟
        - 实际的约束检查等
        """
        self.evaluation_count += 1

        # 这里是你的真实评估逻辑
        # 例如：调用produce_plan.py中的完整优化过程
        result = self._run_full_optimization(x)

        return result

    def _run_full_optimization(self, x: np.ndarray) -> np.ndarray:
        """运行完整的优化过程"""
        # 实际实现会调用你的优化算法
        # 这里只是示例
        return np.array([np.sum(x**2), np.sum((x-2)**2)])


class SurrogateTrainer:
    """代理模型训练器

    整合真实评估、数据收集和模型训练的完整流程。
    """

    def __init__(
        self,
        true_evaluator: TrueEvaluator,
        problem: BlackBoxProblem,
        surrogate_manager: Optional[SurrogateManager] = None,
        **kwargs
    ):
        """
        初始化训练器

        Args:
            true_evaluator: 真实评估函数
            problem: 优化问题定义
            surrogate_manager: 代理模型管理器（可选）
            **kwargs: 其他参数
        """
        self.true_evaluator = true_evaluator
        self.problem = problem
        self._bounds_low, self._bounds_high = get_problem_bounds(problem)
        self._dimension = int(len(self._bounds_low))
        self._n_objectives = get_num_objectives(problem)
        self.surrogate_manager = surrogate_manager or SurrogateManager(problem, **kwargs)

        # 训练配置
        self.config = {
            'initial_samples': kwargs.get('initial_samples', 20),
            'batch_size': kwargs.get('batch_size', 10),
            'max_iterations': kwargs.get('max_iterations', 100),
            'convergence_threshold': kwargs.get('convergence_threshold', 1e-6),
            'evaluation_budget': kwargs.get('evaluation_budget', 1000),
            'checkpoint_interval': kwargs.get('checkpoint_interval', 0),
            'checkpoint_dir': kwargs.get('checkpoint_dir'),
            **kwargs
        }

        # 训练状态
        self.training_data = {
            'X': [],
            'y': [],
            'evaluations': [],
            'surrogate_predictions': [],
            'errors': []
        }

        # 统计
        self.stats = {
            'true_evaluations': 0,
            'surrogate_evaluations': 0,
            'total_time': 0,
            'true_evaluation_time': 0,
            'surrogate_evaluation_time': 0
        }

    def train(
        self,
        X_initial: Optional[np.ndarray] = None,
        y_initial: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        训练代理模型

        Args:
            X_initial: 初始输入数据（可选）
            y_initial: 初始输出数据（可选）

        Returns:
            训练结果
        """
        import time

        start_time = time.time()

        # 1. 初始数据收集
        print("=== 初始数据收集 ===")
        if X_initial is None or y_initial is None:
            X_initial, y_initial = self._collect_initial_samples()

        # 2. 初始训练
        print("\n=== 初始代理模型训练 ===")
        self.surrogate_manager.add_training_data(X_initial, y_initial)

        # 3. 迭代训练
        print(f"\n=== 开始迭代训练（预算: {self.config['evaluation_budget']}）===")
        iteration = 0

        while not self._should_stop(iteration, start_time):
            iteration += 1
            print(f"\n--- 迭代 {iteration} ---")

            # 生成候选解
            candidates = self._generate_candidates()

            # 使用代理模型预评估
            candidates_with_scores = self._evaluate_with_surrogate(candidates)

            # 选择要真实评估的候选解
            selected_candidates = self._select_for_evaluation(candidates_with_scores)

            # 真实评估
            new_X, new_y = self._evaluate_selected(selected_candidates)

            # 更新训练数据
            self.training_data['X'].extend(new_X)
            self.training_data['y'].extend(new_y)

            # 更新代理模型
            self.surrogate_manager.add_training_data(np.array(new_X), np.array(new_y))

            # 评估当前性能
            self._evaluate_iteration(iteration)

            checkpoint_interval = int(self.config.get('checkpoint_interval', 0) or 0)
            checkpoint_dir = self.config.get('checkpoint_dir')
            if checkpoint_interval > 0 and checkpoint_dir:
                if iteration % checkpoint_interval == 0:
                    self.save_checkpoint(checkpoint_dir)

        # 4. 最终训练
        print("\n=== 最终模型训练 ===")
        self._final_training()

        checkpoint_dir = self.config.get('checkpoint_dir')
        if checkpoint_dir:
            self.save_checkpoint(checkpoint_dir)

        total_time = time.time() - start_time
        self.stats['total_time'] = total_time

        print(f"\n训练完成！")
        print(f"总时间: {total_time:.2f}秒")
        print(f"真实评估: {self.stats['true_evaluations']}次")
        print(f"代理评估: {self.stats['surrogate_evaluations']}次")
        print(f"加速比: {self.stats['true_evaluations'] + self.stats['surrogate_evaluations']}/{self.stats['true_evaluations']:.1f}x")

        return self._get_training_results()

    def _collect_initial_samples(self, n_samples: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """收集初始样本"""
        if n_samples is None:
            n_samples = self.config['initial_samples']

        print(f"收集 {n_samples} 个初始样本...")

        X = []
        y = []

        for i in range(n_samples):
            # 生成随机解
            x = np.random.uniform(
                self._bounds_low,
                self._bounds_high,
                size=(self._dimension,)
            )

            # 真实评估
            y_val = self.true_evaluator.evaluate(x)

            X.append(x)
            y.append(y_val)

            if (i + 1) % 5 == 0:
                print(f"  已收集 {i + 1}/{n_samples} 个样本")

        return np.array(X), np.array(y)

    def _generate_candidates(self, n_candidates: int = 100) -> np.ndarray:
        """生成候选解"""
        # 可以使用不同策略生成候选解
        strategies = ['random', 'mutation', 'crossover']
        strategy = np.random.choice(strategies)

        if strategy == 'random':
            return np.random.uniform(
                self._bounds_low,
                self._bounds_high,
                size=(n_candidates, self._dimension)
            )
        elif strategy == 'mutation':
            # 基于现有解变异
            if len(self.training_data['X']) > 0:
                parent = np.random.choice(self.training_data['X'])
                return self._mutate(parent, n_candidates)
            else:
                return self._generate_candidates(n_candidates)
        else:  # crossover
            if len(self.training_data['X']) >= 2:
                parent1, parent2 = np.random.choice(self.training_data['X'], 2, replace=False)
                return self._crossover(parent1, parent2, n_candidates)
            else:
                return self._generate_candidates(n_candidates)

    def _mutate(self, parent: np.ndarray, n_children: int) -> np.ndarray:
        """变异操作"""
        children = []
        for _ in range(n_children):
            child = parent + np.random.normal(0, 0.1, parent.shape)
            # 确保在边界内
            child = np.clip(child, self._bounds_low, self._bounds_high)
            children.append(child)
        return np.array(children)

    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray, n_children: int) -> np.ndarray:
        """交叉操作"""
        children = []
        for _ in range(n_children):
            alpha = np.random.random()
            child = alpha * parent1 + (1 - alpha) * parent2
            # 确保在边界内
            child = np.clip(child, self._bounds_low, self._bounds_high)
            children.append(child)
        return np.array(children)

    def _evaluate_with_surrogate(self, candidates: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray, float]]:
        """使用代理模型评估候选解"""
        import time

        start_time = time.time()
        predictions = self.surrogate_manager.predict(candidates)
        eval_time = time.time() - start_time

        self.stats['surrogate_evaluations'] += len(candidates)
        self.stats['surrogate_evaluation_time'] += eval_time

        # 返回 (候选解, 预测值, 评分)
        candidates_with_scores = []
        for i, candidate in enumerate(candidates):
            if self._n_objectives > 1:
                # 多目标：使用帕累托等级或聚合函数
                score = np.mean(predictions[i])
            else:
                score = predictions[i][0]
            candidates_with_scores.append((candidate, predictions[i], score))

        return candidates_with_scores

    def _select_for_evaluation(
        self,
        candidates_with_scores: List[Tuple[np.ndarray, np.ndarray, float]],
        n_select: Optional[int] = None
    ) -> np.ndarray:
        """选择要真实评估的候选解"""
        if n_select is None:
            n_select = self.config['batch_size']

        if len(candidates_with_scores) <= n_select:
            return np.array([c[0] for c in candidates_with_scores])

        # 使用代理模型的策略选择
        selected = self.surrogate_manager.select_next_evaluations(
            np.array([c[0] for c in candidates_with_scores]),
            n_select
        )

        return selected

    def _evaluate_selected(self, selected_candidates: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """真实评估选中的候选解"""
        import time

        print(f"真实评估 {len(selected_candidates)} 个候选解...")

        X_new = []
        y_new = []

        for i, candidate in enumerate(selected_candidates):
            start_time = time.time()

            # 调用真实的评估函数
            y_val = self.true_evaluator.evaluate(candidate)

            eval_time = time.time() - start_time

            X_new.append(candidate)
            y_new.append(y_val)

            # 记录评估时间
            self.stats['true_evaluations'] += 1
            self.stats['true_evaluation_time'] += eval_time

            # 计算与代理预测的误差
            surrogate_pred = self.surrogate_manager.predict(candidate.reshape(1, -1))[0]
            error = np.linalg.norm(y_val - surrogate_pred)
            self.training_data['errors'].append(error)

            if (i + 1) % 5 == 0:
                print(f"  已评估 {i + 1}/{len(selected_candidates)} 个解")

        return X_new, y_new

    def _should_stop(self, iteration: int, start_time: float) -> bool:
        """判断是否应该停止训练"""
        # 检查评估预算
        if self.stats['true_evaluations'] >= self.config['evaluation_budget']:
            print("达到评估预算上限")
            return True

        # 检查最大迭代次数
        if iteration >= self.config['max_iterations']:
            print("达到最大迭代次数")
            return True

        # 检查收敛性
        if len(self.training_data['errors']) >= 10:
            recent_errors = self.training_data['errors'][-10:]
            if np.std(recent_errors) < self.config['convergence_threshold']:
                print("模型已收敛")
                return True

        # 检查时间预算
        if 'max_time' in self.config:
            elapsed = time.time() - start_time
            if elapsed > self.config['max_time']:
                print("达到时间预算")
                return True

        return False

    def _evaluate_iteration(self, iteration: int):
        """评估当前迭代的性能"""
        if len(self.training_data['errors']) > 0:
            recent_errors = self.training_data['errors'][-10:]
            avg_error = np.mean(recent_errors)
            std_error = np.std(recent_errors)

            print(f"  最近10次评估误差: {avg_error:.4f} ± {std_error:.4f}")
            print(f"  总真实评估: {self.stats['true_evaluations']}")
            print(f"  总代理评估: {self.stats['surrogate_evaluations']}")

        # 评估代理模型质量
        if len(self.training_data['X']) > 50:
            status = self.surrogate_manager.get_status()
            if 'model_quality' in status:
                quality = status['model_quality']
                if isinstance(quality, dict) and 'r2' in quality:
                    print(f"  模型R²: {quality['r2']:.3f}")
                elif isinstance(quality, dict):
                    # 多目标情况
                    r2_values = [v for k, v in quality.items() if 'r2' in k]
                    if r2_values:
                        print(f"  平均模型R²: {np.mean(r2_values):.3f}")

    def _final_training(self):
        """最终训练模型"""
        X_all = np.array(self.training_data['X'])
        y_all = np.array(self.training_data['y'])

        # 使用所有数据重新训练
        self.surrogate_manager.add_training_data(X_all, y_all)

        print(f"最终模型使用 {len(X_all)} 个样本训练")

    def _get_training_results(self) -> Dict[str, Any]:
        """获取训练结果"""
        return {
            'training_data': {
                'n_samples': len(self.training_data['X']),
                'X': np.array(self.training_data['X']),
                'y': np.array(self.training_data['y']),
                'errors': self.training_data['errors']
            },
            'surrogate_model': self.surrogate_manager.surrogate_model,
            'statistics': self.stats,
            'config': self.config
        }

    def _json_safe(self, value):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(v) for v in value]
        return str(value)

    def save_checkpoint(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        model_path = os.path.join(directory, 'surrogate_model.pkl')
        data_path = os.path.join(directory, 'training_data.npz')
        state_path = os.path.join(directory, 'trainer_state.json')

        X = np.asarray(self.training_data.get('X', []))
        y = np.asarray(self.training_data.get('y', []))
        errors = np.asarray(self.training_data.get('errors', []), dtype=float)
        evaluations = np.asarray(self.training_data.get('evaluations', []), dtype=object)
        surrogate_predictions = np.asarray(self.training_data.get('surrogate_predictions', []), dtype=object)
        np.savez_compressed(
            data_path,
            X=X,
            y=y,
            errors=errors,
            evaluations=evaluations,
            surrogate_predictions=surrogate_predictions,
        )

        state = {
            'config': self._json_safe(self.config),
            'stats': self._json_safe(self.stats),
            'meta': {
                'dimension': self._dimension,
                'n_objectives': self._n_objectives,
                'n_samples': int(len(self.training_data.get('X', []))),
            },
        }
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=True, indent=2)

        self.surrogate_manager.save_model(model_path)

    def load_checkpoint(self, directory: str):
        model_path = os.path.join(directory, 'surrogate_model.pkl')
        data_path = os.path.join(directory, 'training_data.npz')
        state_path = os.path.join(directory, 'trainer_state.json')

        if os.path.exists(state_path):
            with open(state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if isinstance(state.get('config'), dict):
                self.config.update(state['config'])
            if isinstance(state.get('stats'), dict):
                self.stats.update(state['stats'])

        if os.path.exists(data_path):
            data = np.load(data_path, allow_pickle=True)
            self.training_data['X'] = list(data.get('X', []))
            self.training_data['y'] = list(data.get('y', []))
            self.training_data['errors'] = list(data.get('errors', []))
            self.training_data['evaluations'] = list(data.get('evaluations', []))
            self.training_data['surrogate_predictions'] = list(data.get('surrogate_predictions', []))

        if os.path.exists(model_path):
            self.surrogate_manager.load_model(model_path)
    def save_trainer(self, filepath: str):
        """保存训练器状态"""
        import pickle

        state = {
            'surrogate_manager': self.surrogate_manager,
            'training_data': self.training_data,
            'stats': self.stats,
            'config': self.config
        }

        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

        print(f"训练器已保存到: {filepath}")

    def load_trainer(self, filepath: str):
        """加载训练器状态"""
        import pickle

        with open(filepath, 'rb') as f:
            state = pickle.load(f)

        self.surrogate_manager = state['surrogate_manager']
        self.training_data = state['training_data']
        self.stats = state['stats']
        self.config = state['config']

        print(f"训练器已从 {filepath} 加载")


# 使用示例
def example_surrogate_training():
    """代理模型训练示例"""
    from nsgablack.core.base import BlackBoxProblem

    # 定义问题
    class ExpensiveProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name='ExpensiveProblem', dimension=10)
            self.bounds = {f'x{i}': [-5.0, 5.0] for i in range(self.dimension)}


        def evaluate(self, x):
            # 模拟昂贵的评估
            import time
            time.sleep(0.1)  # 模拟评估耗时
            x = np.array(x)
            return [np.sum(x**2), np.sum((x-2)**2)]
        def get_num_objectives(self):
            return 2


    # 创建真实评估器
    class MyTrueEvaluator(TrueEvaluator):
        def evaluate(self, x):
            # 这里可以调用任何昂贵的评估
            # 例如：CFD仿真、FEM分析、实际实验等
            x = np.array(x)
            return [np.sum(x**2), np.sum((x-2)**2)]

    # 创建组件
    problem = ExpensiveProblem()
    true_evaluator = MyTrueEvaluator()

    # 创建训练器
    trainer = SurrogateTrainer(
        true_evaluator=true_evaluator,
        problem=problem,
        model_type='random_forest',
        evaluation_budget=100,  # 限制真实评估次数
        batch_size=5  # 每次迭代评估5个候选解
    )

    # 训练代理模型
    results = trainer.train()

    print(f"\n训练结果:")
    print(f"总样本数: {results['training_data']['n_samples']}")
    print(f"平均误差: {np.mean(results['training_data']['errors']):.4f}")

    return trainer, results


if __name__ == "__main__":
    trainer, results = example_surrogate_training()
