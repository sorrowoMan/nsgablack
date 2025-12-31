"""
代理模型策略

定义不同的代理模型使用策略，包括自适应、多目标等。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from ..core.base import BlackBoxProblem
from .base import BaseSurrogateModel


class SurrogateStrategy(ABC):
    """代理模型策略基类"""

    def __init__(self, surrogate_model: BaseSurrogateModel, **kwargs):
        """
        初始化策略

        Args:
            surrogate_model: 代理模型
            **kwargs: 额外参数
        """
        self.surrogate = surrogate_model
        self.config = kwargs

    @abstractmethod
    def should_evaluate(self, x: np.ndarray) -> bool:
        """
        决定是否进行真实评估

        Args:
            x: 解向量

        Returns:
            是否进行真实评估
        """
        pass

    @abstractmethod
    def select_next_samples(
        self,
        candidate_solutions: np.ndarray,
        n_samples: int
    ) -> np.ndarray:
        """
        选择下一个要评估的样本

        Args:
            candidate_solutions: 候选解
            n_samples: 要选择的样本数

        Returns:
            选中的样本
        """
        pass


class RandomStrategy(SurrogateStrategy):
    """随机策略"""

    def __init__(self, surrogate_model: BaseSurrogateModel, **kwargs):
        super().__init__(surrogate_model, **kwargs)
        self.evaluation_ratio = kwargs.get('evaluation_ratio', 0.1)

    def should_evaluate(self, x: np.ndarray) -> bool:
        return np.random.random() < self.evaluation_ratio

    def select_next_samples(
        self,
        candidate_solutions: np.ndarray,
        n_samples: int
    ) -> np.ndarray:
        indices = np.random.choice(
            len(candidate_solutions),
            size=min(n_samples, len(candidate_solutions)),
            replace=False
        )
        return candidate_solutions[indices]


class AdaptiveStrategy(SurrogateStrategy):
    """自适应策略"""

    def __init__(self, surrogate_model: BaseSurrogateModel, **kwargs):
        super().__init__(surrogate_model, **kwargs)
        self.initial_ratio = kwargs.get('initial_ratio', 0.5)
        self.min_ratio = kwargs.get('min_ratio', 0.05)
        self.decay_rate = kwargs.get('decay_rate', 0.99)
        self.current_ratio = self.initial_ratio

    def should_evaluate(self, x: np.ndarray) -> bool:
        # 根据训练进度调整评估比例
        n_samples = len(self.surrogate.X_train)
        if n_samples > 100:
            self.current_ratio *= self.decay_rate
            self.current_ratio = max(self.current_ratio, self.min_ratio)

        return np.random.random() < self.current_ratio

    def select_next_samples(
        self,
        candidate_solutions: np.ndarray,
        n_samples: int
    ) -> np.ndarray:
        # 根据不确定性和预测值选择样本
        if hasattr(self.surrogate, 'predict_uncertainty'):
            # 使用不确定性
            predictions, uncertainties = self.surrogate.predict_uncertainty(candidate_solutions)

            # 平衡探索和利用
            explore_ratio = 0.3
            n_explore = int(n_samples * explore_ratio)
            n_exploit = n_samples - n_explore

            # 探索：高不确定性
            if n_explore > 0:
                explore_indices = np.argsort(uncertainties)[-n_explore:]
            else:
                explore_indices = []

            # 利用：好的预测值
            if n_exploit > 0:
                if self.surrogate.n_objectives > 1:
                    # 多目标：使用支配关系或聚合函数
                    aggregate = np.mean(predictions, axis=1)
                    exploit_indices = np.argsort(aggregate)[:n_exploit]
                else:
                    exploit_indices = np.argsort(predictions.flatten())[:n_exploit]
            else:
                exploit_indices = []

            # 组合选择的样本
            selected_indices = np.unique(np.concatenate([explore_indices, exploit_indices]))

            if len(selected_indices) < n_samples:
                # 补充随机样本
                remaining = n_samples - len(selected_indices)
                available = np.setdiff1d(
                    np.arange(len(candidate_solutions)),
                    selected_indices
                )
                if len(available) > 0:
                    additional = np.random.choice(
                        available,
                        size=min(remaining, len(available)),
                        replace=False
                    )
                    selected_indices = np.concatenate([selected_indices, additional])

            return candidate_solutions[selected_indices]
        else:
            # 没有不确定性预测，使用随机策略
            return RandomStrategy(self.surrogate).select_next_samples(
                candidate_solutions, n_samples
            )


class MultiSurrogateStrategy(SurrogateStrategy):
    """多代理模型策略"""

    def __init__(self, surrogate_models: List[BaseSurrogateModel], **kwargs):
        """
        初始化多代理模型策略

        Args:
            surrogate_models: 代理模型列表
            **kwargs: 额外参数
        """
        # 使用第一个模型作为主要代理
        super().__init__(surrogate_models[0], **kwargs)
        self.surrogates = surrogate_models
        self.weights = kwargs.get('weights', [1.0] * len(surrogate_models))
        self.ensemble_method = kwargs.get('ensemble_method', 'weighted_average')

    def should_evaluate(self, x: np.ndarray) -> bool:
        # 基于所有模型的置信度决定
        confidences = []
        for surrogate in self.surrogates:
            if hasattr(surrogate, 'predict_uncertainty'):
                _, uncertainty = surrogate.predict_uncertainty(x.reshape(1, -1))
                # 简单的置信度计算
                confidence = 1.0 / (1.0 + np.mean(uncertainty))
                confidences.append(confidence)
            else:
                confidences.append(0.5)

        # 加权平均置信度
        weighted_confidence = np.average(confidences, weights=self.weights)

        # 置信度低时进行真实评估
        return weighted_confidence < 0.7

    def select_next_samples(
        self,
        candidate_solutions: np.ndarray,
        n_samples: int
    ) -> np.ndarray:
        # 收集所有模型的预测
        all_predictions = []
        all_uncertainties = []

        for surrogate in self.surrogates:
            if hasattr(surrogate, 'predict_uncertainty'):
                pred, unc = surrogate.predict_uncertainty(candidate_solutions)
            else:
                pred = surrogate.predict(candidate_solutions)
                unc = np.zeros_like(pred)

            all_predictions.append(pred)
            all_uncertainties.append(unc)

        # 集成预测和不确定性
        if self.ensemble_method == 'weighted_average':
            # 加权平均
            ensemble_pred = np.average(all_predictions, axis=0, weights=self.weights)
            ensemble_unc = np.average(all_uncertainties, axis=0, weights=self.weights)
        elif self.ensemble_method == 'variance':
            # 方差作为不确定性
            ensemble_pred = np.mean(all_predictions, axis=0)
            ensemble_unc = np.var(all_predictions, axis=0)
        else:
            # 简单平均
            ensemble_pred = np.mean(all_predictions, axis=0)
            ensemble_unc = np.mean(all_uncertainties, axis=0)

        # 基于集成不确定性选择样本
        if ensemble_unc.shape[1] == 1:
            uncertainties = ensemble_unc.flatten()
        else:
            uncertainties = np.mean(ensemble_unc, axis=1)

        # 选择不确定性最高的样本
        indices = np.argsort(uncertainties)[-n_samples:]
        return candidate_solutions[indices]


class BayesianStrategy(SurrogateStrategy):
    """贝叶斯优化策略"""

    def __init__(self, surrogate_model: BaseSurrogateModel, **kwargs):
        super().__init__(surrogate_model, **kwargs)
        self.acquisition_func = kwargs.get('acquisition_func', 'ei')  # Expected Improvement
        self.exploration_weight = kwargs.get('exploration_weight', 0.01)

    def should_evaluate(self, x: np.ndarray) -> bool:
        # 贝叶斯策略总是使用代理模型选择
        return True

    def select_next_samples(
        self,
        candidate_solutions: np.ndarray,
        n_samples: int
    ) -> np.ndarray:
        # 计算采集函数值
        if self.acquisition_func == 'ei':
            acquisition_values = self._expected_improvement(candidate_solutions)
        elif self.acquisition_func == 'ucb':
            acquisition_values = self._upper_confidence_bound(candidate_solutions)
        elif self.acquisition_func == 'poi':
            acquisition_values = self._probability_of_improvement(candidate_solutions)
        else:
            raise ValueError(f"未知的采集函数: {self.acquisition_func}")

        # 选择采集函数值最高的样本
        indices = np.argsort(acquisition_values)[-n_samples:]
        return candidate_solutions[indices]

    def _expected_improvement(self, X: np.ndarray) -> np.ndarray:
        """计算期望改进"""
        if not hasattr(self.surrogate, 'predict_uncertainty'):
            # 如果模型不支持不确定性预测，使用随机策略
            return np.random.random(len(X))

        pred, std = self.surrogate.predict_uncertainty(X)

        # 当前最佳值（假设是最小化）
        if len(self.surrogate.y_train) > 0:
            if self.surrogate.n_objectives > 1:
                # 多目标：使用帕累托前沿
                y_train = np.array(self.surrogate.y_train)
                pareto = self._find_pareto_front(y_train)
                best_values = np.min(pareto, axis=0)
                # 简化：使用加权求和
                weights = np.ones(self.surrogate.n_objectives) / self.surrogate.n_objectives
                best_value = np.sum(best_values * weights)
                pred_weighted = np.sum(pred * weights, axis=1)
            else:
                best_value = np.min(self.surrogate.y_train)
                pred_weighted = pred.flatten()
        else:
            return np.zeros(len(X))

        # 计算EI
        improvement = best_value - pred_weighted
        Z = improvement / (std + 1e-8)
        ei = improvement * self._norm_cdf(Z) + std * self._norm_pdf(Z)

        return ei

    def _upper_confidence_bound(self, X: np.ndarray) -> np.ndarray:
        """计算上置信界"""
        pred, std = self.surrogate.predict_uncertainty(X)

        if self.surrogate.n_objectives > 1:
            # 多目标：使用聚合
            pred_agg = np.mean(pred, axis=1)
        else:
            pred_agg = pred.flatten()

        ucb = pred_agg + self.exploration_weight * std.flatten()
        return ucb

    def _probability_of_improvement(self, X: np.ndarray) -> np.ndarray:
        """计算改进概率"""
        pred, std = self.surrogate.predict_uncertainty(X)

        if len(self.surrogate.y_train) > 0:
            if self.surrogate.n_objectives > 1:
                best_value = np.min(np.mean(np.array(self.surrogate.y_train), axis=1))
                pred_weighted = np.mean(pred, axis=1)
            else:
                best_value = np.min(self.surrogate.y_train)
                pred_weighted = pred.flatten()
        else:
            return np.ones(len(X))

        improvement = best_value - pred_weighted
        Z = improvement / (std + 1e-8)
        poi = self._norm_cdf(Z)

        return poi

    def _norm_cdf(self, x: np.ndarray) -> np.ndarray:
        """标准正态分布CDF"""
        return 0.5 * (1 + np.erf(x / np.sqrt(2)))

    def _norm_pdf(self, x: np.ndarray) -> np.ndarray:
        """标准正态分布PDF"""
        return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

    def _find_pareto_front(self, y: np.ndarray) -> np.ndarray:
        """找到帕累托前沿"""
        pareto = []
        for i, point in enumerate(y):
            dominated = False
            for j, other in enumerate(y):
                if i != j and np.all(other <= point) and np.any(other < point):
                    dominated = True
                    break
            if not dominated:
                pareto.append(point)
        return np.array(pareto)


class SurrogateStrategyFactory:
    """代理模型策略工厂"""

    @staticmethod
    def create_strategy(
        strategy_type: str,
        surrogate_model: BaseSurrogateModel,
        **kwargs
    ) -> SurrogateStrategy:
        """
        创建策略

        Args:
            strategy_type: 策略类型
            surrogate_model: 代理模型
            **kwargs: 额外参数

        Returns:
            策略实例
        """
        if strategy_type == 'random':
            return RandomStrategy(surrogate_model, **kwargs)
        elif strategy_type == 'adaptive':
            return AdaptiveStrategy(surrogate_model, **kwargs)
        elif strategy_type == 'bayesian':
            return BayesianStrategy(surrogate_model, **kwargs)
        elif strategy_type == 'multi':
            surrogate_models = kwargs.get('surrogate_models', [surrogate_model])
            return MultiSurrogateStrategy(surrogate_models, **kwargs)
        else:
            raise ValueError(f"未知的策略类型: {strategy_type}")