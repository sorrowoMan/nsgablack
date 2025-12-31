"""
建议者（Advisor）建议策略

通过分析当前解的分布和趋势，预测可能的最优区域，
向其他智能体提供建议。支持多种建议方法：
- 贝叶斯优化建议
- 机器学习预测
- 统计趋势分析
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class AdvisoryMethod(Enum):
    """建议方法枚举"""
    BAYESIAN = "bayesian"           # 贝叶斯优化
    GAUSSIAN_PROCESS = "gaussian_process"  # 高斯过程
    RANDOM_FOREST = "random_forest"  # 随机森林
    NEURAL_NETWORK = "neural_network"  # 神经网络
    STATISTICAL = "statistical"      # 统计分析
    ENSEMBLE = "ensemble"            # 集成方法


@dataclass
class Advisory:
    """建议数据结构"""
    suggested_region: np.ndarray       # 建议的搜索区域中心
    region_radius: float               # 搜索区域半径
    confidence: float                  # 建议的置信度 [0, 1]
    method: AdvisoryMethod             # 使用的建议方法
    reasoning: str                     # 建议理由
    predicted_improvement: float       # 预期改进幅度
    target_agents: List[str]           # 目标智能体列表


class BaseAdvisoryStrategy(ABC):
    """建议策略基类"""

    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.history = []
        self.performance_metrics = []

    @abstractmethod
    def analyze_solutions(self,
                         population: np.ndarray,
                         objectives: List[List[float]],
                         constraints: List[List[float]] = None) -> Dict[str, Any]:
        """
        分析当前解的分布

        Args:
            population: 种群个体 [N, D]
            objectives: 目标值 [N, M]
            constraints: 约束违背度 [N, C]

        Returns:
            分析结果字典
        """
        pass

    @abstractmethod
    def generate_advisory(self,
                         analysis: Dict[str, Any],
                         context: Dict[str, Any]) -> Advisory:
        """
        生成建议

        Args:
            analysis: 分析结果
            context: 上下文信息（代数、历史等）

        Returns:
            Advisory: 建议对象
        """
        pass

    def update_performance(self, advisory: Advisory, actual_improvement: float):
        """更新建议性能指标"""
        self.performance_metrics.append({
            'advisory': advisory,
            'improvement': actual_improvement,
            'confidence': advisory.confidence
        })


class BayesianAdvisoryStrategy(BaseAdvisoryStrategy):
    """
    贝叶斯建议策略

    使用贝叶斯优化（高斯过程）预测最优搜索区域
    """

    def __init__(self, config: Dict = None):
        super().__init__("Bayesian Advisory", config)

        # 默认配置
        default_config = {
            'acquisition_function': 'expected_improvement',  # 采集函数
            'kernel': 'rbf',                                  # 核函数
            'n_candidates': 10,                               # 候选解数量
            'exploration_weight': 0.1,                        # 探索权重
        }
        default_config.update(self.config)
        self.config = default_config

        # 高斯过程模型（延迟初始化）
        self.gp_model = None
        self.model_fitted = False

    def analyze_solutions(self,
                         population: np.ndarray,
                         objectives: List[List[float]],
                         constraints: List[List[float]] = None) -> Dict[str, Any]:
        """分析解分布并拟合高斯过程"""
        n_samples, n_dim = population.shape
        n_obj = len(objectives[0]) if objectives else 1

        # 转换为numpy数组
        X = np.array(population)
        Y = np.array(objectives)

        # 如果是多目标，转换为标量（加权和）
        if n_obj > 1:
            # 使用归一化和加权
            Y_norm = (Y - Y.min(axis=0)) / (Y.max(axis=0) - Y.min(axis=0) + 1e-10)
            Y_scalar = Y_norm.mean(axis=1)
        else:
            Y_scalar = Y.flatten()

        # 拟合高斯过程
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel

            # 定义核函数
            kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)

            # 创建和拟合模型
            self.gp_model = GaussianProcessRegressor(
                kernel=kernel,
                alpha=1e-6,
                normalize_y=True,
                n_restarts_optimizer=10
            )
            self.gp_model.fit(X, Y_scalar)
            self.model_fitted = True

        except ImportError:
            # 如果sklearn不可用，使用简单的统计分析
            self.model_fitted = False

        # 统计分析
        analysis = {
            'mean': np.mean(X, axis=0),
            'std': np.std(X, axis=0),
            'best_idx': np.argmin(Y_scalar),
            'worst_idx': np.argmax(Y_scalar),
            'diversity': np.std(X, axis=0).mean(),
            'n_samples': n_samples,
            'n_dim': n_dim,
            'objectives_range': (Y.min(axis=0), Y.max(axis=0))
        }

        return analysis

    def generate_advisory(self,
                         analysis: Dict[str, Any],
                         context: Dict[str, Any]) -> Advisory:
        """使用贝叶斯优化生成建议"""
        if not self.model_fitted:
            # 如果模型未拟合，使用简单统计
            return self._generate_statistical_advisory(analysis, context)

        # 生成候选解（在当前解附近）
        n_candidates = self.config['n_candidates']
        current_mean = analysis['mean']
        current_std = analysis['std']

        # 采样候选点
        candidates = np.random.randn(n_candidates, len(current_mean))
        candidates = candidates * current_std * 2 + current_mean

        # 使用高斯过程预测
        mean_pred, std_pred = self.gp_model.predict(candidates, return_std=True)

        # 计算采集函数值
        if self.config['acquisition_function'] == 'expected_improvement':
            # 期望改进（EI）
            current_best = mean_pred.min()
            ei = (current_best - mean_pred) * std_pred  # 简化版
            best_idx = np.argmax(ei)
        else:
            # 置信下界（LCB）
            lcb = mean_pred - 1.96 * std_pred
            best_idx = np.argmin(lcb)

        suggested_region = candidates[best_idx]

        # 计算置信度
        confidence = min(1.0, std_pred[best_idx] / (std_pred.mean() + 1e-10))

        # 预测改进
        predicted_improvement = abs(mean_pred[best_idx] - mean_pred.mean())

        return Advisory(
            suggested_region=suggested_region,
            region_radius=current_std.mean() * 0.5,
            confidence=confidence,
            method=AdvisoryMethod.BAYESIAN,
            reasoning=f"贝叶斯优化预测EI最高的区域，置信度{confidence:.2%}",
            predicted_improvement=predicted_improvement,
            target_agents=['explorer', 'exploiter']
        )

    def _generate_statistical_advisory(self,
                                       analysis: Dict,
                                       context: Dict) -> Advisory:
        """生成基于统计的建议（后备方案）"""
        # 向最优解方向移动
        mean = analysis['mean']
        std = analysis['std']

        suggested_region = mean + std * 0.5  # 向探索方向移动

        return Advisory(
            suggested_region=suggested_region,
            region_radius=std.mean() * 0.3,
            confidence=0.5,
            method=AdvisoryMethod.STATISTICAL,
            reasoning="基于统计趋势建议探索均值+0.5标准差区域",
            predicted_improvement=std.mean() * 0.2,
            target_agents=['explorer']
        )


class MLAdvisoryStrategy(BaseAdvisoryStrategy):
    """
    机器学习建议策略

    使用ML模型学习解分布与目标值的关系
    """

    def __init__(self, config: Dict = None):
        super().__init__("ML Advisory", config)

        default_config = {
            'model_type': 'random_forest',  # 模型类型
            'n_estimators': 100,
            'max_depth': 10,
            'retrain_interval': 10,         # 重训练间隔
        }
        default_config.update(self.config)
        self.config = default_config

        self.ml_model = None
        self.model_fitted = False
        self.last_retrain_gen = 0

    def analyze_solutions(self,
                         population: np.ndarray,
                         objectives: List[List[float]],
                         constraints: List[List[float]] = None) -> Dict[str, Any]:
        """分析解分布并训练ML模型"""
        X = np.array(population)
        Y = np.array(objectives)

        # 多目标转标量
        if Y.ndim > 1 and Y.shape[1] > 1:
            Y_norm = (Y - Y.min(axis=0)) / (Y.max(axis=0) - Y.min(axis=0) + 1e-10)
            Y_scalar = Y_norm.mean(axis=1)
        else:
            Y_scalar = Y.flatten()

        # 训练模型
        try:
            if self.config['model_type'] == 'random_forest':
                from sklearn.ensemble import RandomForestRegressor

                self.ml_model = RandomForestRegressor(
                    n_estimators=self.config['n_estimators'],
                    max_depth=self.config['max_depth'],
                    random_state=42
                )
            elif self.config['model_type'] == 'gradient_boosting':
                from sklearn.ensemble import GradientBoostingRegressor

                self.ml_model = GradientBoostingRegressor(
                    n_estimators=self.config['n_estimators'],
                    max_depth=self.config['max_depth'],
                    random_state=42
                )

            self.ml_model.fit(X, Y_scalar)
            self.model_fitted = True

            # 特征重要性
            feature_importance = self.ml_model.feature_importances_

        except (ImportError, Exception):
            self.model_fitted = False
            feature_importance = None

        analysis = {
            'mean': np.mean(X, axis=0),
            'std': np.std(X, axis=0),
            'best_idx': np.argmin(Y_scalar),
            'feature_importance': feature_importance,
            'model_type': self.config['model_type']
        }

        return analysis

    def generate_advisory(self,
                         analysis: Dict[str, Any],
                         context: Dict[str, Any]) -> Advisory:
        """使用ML模型生成建议"""
        if not self.model_fitted or analysis['feature_importance'] is None:
            # 后备方案
            return BayesianAdvisoryStrategy()._generate_statistical_advisory(analysis, context)

        # 生成候选解
        n_candidates = 20
        mean = analysis['mean']
        std = analysis['std']

        # 基于特征重要性生成候选
        feature_importance = analysis['feature_importance']
        important_dims = feature_importance > feature_importance.mean()

        candidates = []
        for _ in range(n_candidates):
            candidate = mean.copy()
            # 在重要维度上更大变异
            for i in range(len(mean)):
                if important_dims[i]:
                    candidate[i] += np.random.randn() * std[i] * 0.8
                else:
                    candidate[i] += np.random.randn() * std[i] * 0.3
            candidates.append(candidate)

        candidates = np.array(candidates)

        # 使用ML模型预测
        predictions = self.ml_model.predict(candidates)
        best_idx = np.argmin(predictions)

        suggested_region = candidates[best_idx]
        confidence = min(1.0, abs(predictions[best_idx] - predictions.mean()) /
                       (predictions.std() + 1e-10))

        return Advisory(
            suggested_region=suggested_region,
            region_radius=std[important_dims].mean() * 0.4,
            confidence=confidence,
            method=AdvisoryMethod.RANDOM_FOREST if self.config['model_type'] == 'random_forest'
                  else AdvisoryMethod.NEURAL_NETWORK,
            reasoning=f"ML模型({self.config['model_type']})预测的最优区域，"
                      f"重点关注{important_dims.sum()}个关键特征",
            predicted_improvement=abs(predictions[best_idx] - predictions.mean()),
            target_agents=['exploiter', 'explorer']
        )


class EnsembleAdvisoryStrategy(BaseAdvisoryStrategy):
    """
    集成建议策略

    组合多种建议方法，提高鲁棒性
    """

    def __init__(self, config: Dict = None):
        super().__init__("Ensemble Advisory", config)

        default_config = {
            'strategies': ['bayesian', 'ml'],
            'voting': 'weighted',  # 'weighted', 'majority', 'best'
            'weights': {'bayesian': 0.6, 'ml': 0.4}
        }
        default_config.update(self.config)
        self.config = default_config

        # 初始化子策略
        self.strategies = []
        if 'bayesian' in self.config['strategies']:
            self.strategies.append(BayesianAdvisoryStrategy())
        if 'ml' in self.config['strategies']:
            self.strategies.append(MLAdvisoryStrategy())

    def analyze_solutions(self,
                         population: np.ndarray,
                         objectives: List[List[float]],
                         constraints: List[List[float]] = None) -> Dict[str, Any]:
        """组合所有策略的分析结果"""
        all_analysis = {}
        for strategy in self.strategies:
            analysis = strategy.analyze_solutions(population, objectives, constraints)
            all_analysis[strategy.name] = analysis

        # 合并分析结果
        combined_analysis = {
            'individual': all_analysis,
            'n_strategies': len(self.strategies)
        }

        return combined_analysis

    def generate_advisory(self,
                         analysis: Dict[str, Any],
                         context: Dict[str, Any]) -> Advisory:
        """集成所有策略生成最终建议"""
        # 从各个策略获取建议
        advisories = []
        for strategy in self.strategies:
            if 'individual' in analysis:
                strat_analysis = analysis['individual'].get(strategy.name, {})
                if strat_analysis:
                    advisory = strategy.generate_advisory(strat_analysis, context)
                    advisories.append(advisory)

        if not advisories:
            # 后备方案
            return BayesianAdvisoryStrategy()._generate_statistical_advisory(
                list(analysis['individual'].values())[0] if analysis.get('individual') else {}, context
            )

        # 集成建议
        if self.config['voting'] == 'weighted':
            # 加权平均
            weights = list(self.config['weights'].values())[:len(advisories)]
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]

            suggested_region = sum(w * adv.suggested_region for w, adv in zip(weights, advisories))
            confidence = sum(w * adv.confidence for w, adv in zip(weights, advisories))
            region_radius = sum(w * adv.region_radius for w, adv in zip(weights, advisories))
            predicted_improvement = sum(w * adv.predicted_improvement for w, adv in zip(weights, advisories))

            # 合并目标智能体
            all_targets = set()
            for adv in advisories:
                all_targets.update(adv.target_agents)
            target_agents = list(all_targets)

        elif self.config['voting'] == 'best':
            # 选择最佳建议
            best_adv = max(advisories, key=lambda a: a.confidence * a.predicted_improvement)
            return best_adv

        else:  # majority
            # 多数投票（简化：选择中间值）
            suggested_region = np.median([adv.suggested_region for adv in advisories], axis=0)
            confidence = np.mean([adv.confidence for adv in advisories])
            region_radius = np.mean([adv.region_radius for adv in advisories])
            predicted_improvement = np.mean([adv.predicted_improvement for adv in advisories])
            target_agents = ['explorer', 'exploiter']

        return Advisory(
            suggested_region=suggested_region,
            region_radius=region_radius,
            confidence=min(1.0, confidence),
            method=AdvisoryMethod.ENSEMBLE,
            reasoning=f"集成{len(advisories)}种策略的加权建议：{', '.join([adv.method.value for adv in advisories])}",
            predicted_improvement=predicted_improvement,
            target_agents=target_agents
        )


class AdvisoryStrategyFactory:
    """建议策略工厂"""

    _strategies = {
        'bayesian': BayesianAdvisoryStrategy,
        'ml': MLAdvisoryStrategy,
        'random_forest': lambda cfg: MLAdvisoryStrategy({**(cfg or {}), 'model_type': 'random_forest'}),
        'ensemble': EnsembleAdvisoryStrategy,
    }

    @classmethod
    def create_strategy(cls, method: str, config: Dict = None) -> BaseAdvisoryStrategy:
        """创建建议策略"""
        method_lower = method.lower()

        if method_lower in cls._strategies:
            strategy_class = cls._strategies[method_lower]
            return strategy_class(config)
        else:
            raise ValueError(f"未知的建议方法: {method}. 可用方法: {list(cls._strategies.keys())}")

    @classmethod
    def register_strategy(cls, name: str, strategy_class: type):
        """注册新的建议策略"""
        cls._strategies[name.lower()] = strategy_class


# 便捷函数
def create_advisory_strategy(method: str = 'bayesian', config: Dict = None) -> BaseAdvisoryStrategy:
    """
    创建建议策略的便捷函数

    Args:
        method: 建议方法 ('bayesian', 'ml', 'ensemble')
        config: 配置字典

    Returns:
        BaseAdvisoryStrategy: 建议策略实例

    Example:
        >>> strategy = create_advisory_strategy('bayesian')
        >>> analysis = strategy.analyze_solutions(population, objectives)
        >>> advisory = strategy.generate_advisory(analysis, context)
        >>> print(f"建议区域: {advisory.suggested_region}")
        >>> print(f"置信度: {advisory.confidence:.2%}")
    """
    return AdvisoryStrategyFactory.create_strategy(method, config)
