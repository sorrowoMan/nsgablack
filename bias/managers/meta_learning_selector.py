"""
基于评估框架的元学习偏置选择器
利用历史偏置效果数据训练代理模型，为新问题推荐最优偏置组合
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
import logging
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import warnings
warnings.filterwarnings('ignore')

from .analytics import BiasEffectivenessAnalyzer, BiasEffectivenessMetrics
from ..core.base import AlgorithmicBias, DomainBias
from ..bias_library_algorithmic import AlgorithmicBiasFactory
from ..bias_v2 import DomainBiasFactory


@dataclass
class ProblemFeatures:
    """问题特征描述"""
    problem_id: str
    problem_type: str  # 'continuous', 'discrete', 'mixed', 'combinatorial'
    dimension: int
    num_objectives: int
    constraint_count: int

    # 问题复杂度特征
    multimodality: float  # 多峰性 (0-1)
    separability: float   # 可分离性 (0-1)
    ruggedness: float     # 粗糙度 (0-1)
    landscape_noise: float  # 噪声水平 (0-1)

    # 问题规模特征
    search_space_size: float
    constraint_density: float
    feasible_region_ratio: float

    # 计算特征
    evaluation_cost: float  # 单次评估成本
    max_evaluations: int    # 最大评估次数


@dataclass
class BiasRecommendation:
    """偏置推荐结果"""
    algorithmic_biases: Dict[str, float]  # bias_name: weight
    domain_biases: Dict[str, float]       # bias_name: weight
    confidence_score: float               # 推荐置信度 (0-1)
    expected_improvement: float           # 预期改进百分比
    reasoning: List[str]                  # 推荐理由
    alternative_suggestions: List[Dict]   # 备选方案


class ProblemFeatureExtractor:
    """问题特征提取器"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names = [
            'dimension', 'num_objectives', 'constraint_count',
            'multimodality', 'separability', 'ruggedness', 'landscape_noise',
            'search_space_size', 'constraint_density', 'feasible_region_ratio',
            'evaluation_cost', 'max_evaluations'
        ]

    def extract_features(self, problem_instance: Any, sample_solutions: List = None) -> ProblemFeatures:
        """
        从问题实例提取特征
        """
        # 基础特征（需要从问题实例获取）
        dimension = getattr(problem_instance, 'dimension', 10)
        num_objectives = getattr(problem_instance, 'num_objectives', 1)
        constraint_count = getattr(problem_instance, 'constraint_count', 0)

        # 问题类型推断
        problem_type = self._infer_problem_type(problem_instance)

        # 复杂度特征估计
        complexity_features = self._estimate_complexity_features(
            problem_instance, sample_solutions)

        # 规模特征
        scale_features = self._estimate_scale_features(problem_instance)

        # 计算特征
        computation_features = self._estimate_computation_features(problem_instance)

        return ProblemFeatures(
            problem_id=getattr(problem_instance, 'name', 'unknown'),
            problem_type=problem_type,
            dimension=dimension,
            num_objectives=num_objectives,
            constraint_count=constraint_count,
            **complexity_features,
            **scale_features,
            **computation_features
        )

    def _infer_problem_type(self, problem) -> str:
        """推断问题类型"""
        # 简化的类型推断逻辑
        if hasattr(problem, 'is_discrete') and problem.is_discrete:
            if hasattr(problem, 'graph_structure'):
                return 'combinatorial'
            else:
                return 'discrete'
        elif hasattr(problem, 'is_mixed') and problem.is_mixed:
            return 'mixed'
        else:
            return 'continuous'

    def _estimate_complexity_features(self, problem, sample_solutions: List = None) -> Dict[str, float]:
        """估计复杂度特征"""
        # 这里是简化实现，实际可能需要采样分析
        return {
            'multimodality': 0.5,  # 默认中等多峰性
            'separability': 0.7,   # 默认较高可分离性
            'ruggedness': 0.3,     # 默认中等粗糙度
            'landscape_noise': 0.1  # 默认低噪声
        }

    def _estimate_scale_features(self, problem) -> Dict[str, float]:
        """估计规模特征"""
        dimension = getattr(problem, 'dimension', 10)
        bounds = getattr(problem, 'bounds', None)

        if bounds:
            search_space_size = np.prod([b[1] - b[0] for b in bounds])
        else:
            search_space_size = 100 ** dimension  # 默认每维100单位

        return {
            'search_space_size': np.log10(search_space_size + 1),
            'constraint_density': getattr(problem, 'constraint_count', 0) / dimension,
            'feasible_region_ratio': 0.8  # 默认80%可行域
        }

    def _estimate_computation_features(self, problem) -> Dict[str, float]:
        """估计计算特征"""
        return {
            'evaluation_cost': 1.0,  # 默认单位成本
            'max_evaluations': 10000  # 默认最大评估次数
        }


class MetaLearningBiasSelector:
    """元学习偏置选择器"""

    def __init__(self, model_save_path: str = "bias_meta_model"):
        """
        Args:
            model_save_path: 模型保存路径
        """
        self.model_save_path = model_save_path
        self.feature_extractor = ProblemFeatureExtractor()

        # 预测模型集合
        self.models = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'neural_network': MLPRegressor(hidden_layer_sizes=(50, 25), random_state=42, max_iter=500)
        }

        # 偏置类型编码器
        self.bias_encoder = LabelEncoder()
        self.scaler = StandardScaler()

        # 历史数据库
        self.problem_database: List[Dict] = []
        self.bias_performance_db: Dict[str, List[BiasEffectivenessMetrics]] = defaultdict(list)

        # 可用偏置池
        self.available_algorithmic_biases = list(AlgorithmicBiasFactory.get_available_types())
        self.available_domain_biases = list(DomainBiasFactory.get_available_types())

        self.logger = logging.getLogger(__name__)

    def add_historical_data(self, problem_features: ProblemFeatures,
                          bias_metrics: Dict[str, BiasEffectivenessMetrics]):
        """添加历史数据"""
        # 添加问题数据
        problem_data = {
            'features': problem_features,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        self.problem_database.append(problem_data)

        # 添加偏置效果数据
        for bias_name, metrics in bias_metrics.items():
            self.bias_performance_db[bias_name].append(metrics)

        self.logger.info(f"Added historical data for problem: {problem_features.problem_id}")

    def train_models(self) -> Dict[str, float]:
        """训练元学习模型"""
        if len(self.problem_database) < 10:
            self.logger.warning("Insufficient historical data for training (need at least 10 problems)")
            return {'error': 'Insufficient data'}

        # 准备训练数据
        X_train, y_train_dict = self._prepare_training_data()

        if X_train is None or len(X_train) == 0:
            return {'error': 'Failed to prepare training data'}

        # 训练结果
        training_results = {}

        # 为每个性能指标训练模型
        for target_metric, y_train in y_train_dict.items():
            self.logger.info(f"Training models for target: {target_metric}")

            metric_results = {}
            for model_name, model in self.models.items():
                try:
                    # 训练模型
                    model.fit(X_train, y_train)

                    # 交叉验证评估
                    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')

                    # 测试集评估
                    X_train_split, X_test, y_train_split, y_test = train_test_split(
                        X_train, y_train, test_size=0.2, random_state=42)
                    model.fit(X_train_split, y_train_split)
                    y_pred = model.predict(X_test)
                    test_r2 = r2_score(y_test, y_pred)

                    metric_results[model_name] = {
                        'cv_score': np.mean(cv_scores),
                        'cv_std': np.std(cv_scores),
                        'test_r2': test_r2
                    }

                    self.logger.info(f"  {model_name}: CV={np.mean(cv_scores):.3f}±{np.std(cv_scores):.3f}, Test={test_r2:.3f}")

                except Exception as e:
                    self.logger.error(f"Error training {model_name} for {target_metric}: {e}")
                    metric_results[model_name] = {'error': str(e)}

            training_results[target_metric] = metric_results

        # 保存模型
        self._save_models()

        return training_results

    def recommend_biases(self, problem_features: ProblemFeatures,
                        optimization_goal: str = 'balanced',
                        top_k: int = 5) -> BiasRecommendation:
        """
        为新问题推荐偏置组合

        Args:
            problem_features: 问题特征
            optimization_goal: 优化目标 ('convergence', 'quality', 'balanced')
            top_k: 推荐的偏置数量
        """
        # 检查是否有训练好的模型
        if not self._models_trained():
            self.logger.warning("No trained models available, using heuristic recommendation")
            return self._heuristic_recommendation(problem_features, optimization_goal, top_k)

        # 提取特征
        features = self._extract_feature_vector(problem_features)
        features_scaled = self.scaler.transform([features])

        # 预测偏置效果
        algorithmic_predictions = self._predict_bias_effects(
            features_scaled[0], self.available_algorithmic_biases)
        domain_predictions = self._predict_bias_effects(
            features_scaled[0], self.available_domain_biases)

        # 根据优化目标选择偏置
        selected_algorithmic = self._select_top_biases(
            algorithmic_predictions, optimization_goal, top_k)
        selected_domain = self._select_top_biases(
            domain_predictions, optimization_goal, top_k // 2)

        # 计算权重
        algorithmic_weights = self._compute_bias_weights(selected_algorithmic)
        domain_weights = self._compute_bias_weights(selected_domain)

        # 生成推荐理由
        reasoning = self._generate_reasoning(
            problem_features, selected_algorithmic, selected_domain, optimization_goal)

        # 计算置信度
        confidence = self._compute_confidence(
            algorithmic_predictions, domain_predictions, problem_features)

        # 计算预期改进
        expected_improvement = self._estimate_expected_improvement(
            selected_algorithmic, selected_domain, algorithmic_predictions, domain_predictions)

        # 生成备选方案
        alternatives = self._generate_alternatives(
            algorithmic_predictions, domain_predictions, optimization_goal, top_k)

        return BiasRecommendation(
            algorithmic_biases=algorithmic_weights,
            domain_biases=domain_weights,
            confidence_score=confidence,
            expected_improvement=expected_improvement,
            reasoning=reasoning,
            alternative_suggestions=alternatives
        )

    def _prepare_training_data(self) -> Tuple[Optional[np.ndarray], Dict[str, np.ndarray]]:
        """准备训练数据"""
        if len(self.problem_database) == 0:
            return None, {}

        # 准备特征矩阵
        X = []
        y_convergence = []
        y_quality = []
        y_diversity = []
        y_overall = []

        for problem_data in self.problem_database:
            features = problem_data['features']
            feature_vector = self._extract_feature_vector(features)
            X.append(feature_vector)

            # 获取该问题的最佳偏置效果
            best_metrics = self._get_best_bias_metrics_for_problem(features.problem_id)

            if best_metrics:
                y_convergence.append(best_metrics.convergence_improvement)
                y_quality.append(best_metrics.solution_quality_boost)
                y_diversity.append(best_metrics.diversity_score)
                y_overall.append(self._compute_overall_score(best_metrics))

        if len(X) == 0:
            return None, {}

        X = np.array(X)
        X_scaled = self.scaler.fit_transform(X)

        y_dict = {
            'convergence': np.array(y_convergence),
            'quality': np.array(y_quality),
            'diversity': np.array(y_diversity),
            'overall': np.array(y_overall)
        }

        return X_scaled, y_dict

    def _extract_feature_vector(self, problem_features: ProblemFeatures) -> List[float]:
        """提取特征向量"""
        return [
            problem_features.dimension,
            problem_features.num_objectives,
            problem_features.constraint_count,
            problem_features.multimodality,
            problem_features.separability,
            problem_features.ruggedness,
            problem_features.landscape_noise,
            problem_features.search_space_size,
            problem_features.constraint_density,
            problem_features.feasible_region_ratio,
            problem_features.evaluation_cost,
            problem_features.max_evaluations
        ]

    def _predict_bias_effects(self, features: np.ndarray, bias_types: List[str]) -> Dict[str, Dict[str, float]]:
        """预测偏置效果"""
        predictions = {}

        for bias_type in bias_types:
            # 这里简化处理，实际需要为每个偏置类型单独训练模型
            # 或者使用偏置类型作为输入特征

            # 使用随机森林模型预测各项指标
            try:
                convergence_pred = self.models['random_forest'].predict([features])[0]
                quality_pred = self.models['gradient_boost'].predict([features])[0]
                diversity_pred = self.models['neural_network'].predict([features])[0]

                # 添加一些基于偏置类型的启发式调整
                bias_modifier = self._get_bias_type_modifier(bias_type)

                predictions[bias_type] = {
                    'convergence': convergence_pred * bias_modifier.get('convergence', 1.0),
                    'quality': quality_pred * bias_modifier.get('quality', 1.0),
                    'diversity': diversity_pred * bias_modifier.get('diversity', 1.0),
                    'overall': (convergence_pred + quality_pred + diversity_pred) / 3
                }
            except Exception as e:
                self.logger.warning(f"Failed to predict effects for bias {bias_type}: {e}")
                predictions[bias_type] = {
                    'convergence': 0.0, 'quality': 0.0, 'diversity': 0.0, 'overall': 0.0
                }

        return predictions

    def _get_bias_type_modifier(self, bias_type: str) -> Dict[str, float]:
        """获取偏置类型的调整因子"""
        modifiers = {
            'DiversityBias': {'convergence': 0.7, 'quality': 1.0, 'diversity': 1.5},
            'ConvergenceBias': {'convergence': 1.5, 'quality': 1.2, 'diversity': 0.8},
            'ExplorationBias': {'convergence': 0.8, 'quality': 1.1, 'diversity': 1.3},
            'PrecisionBias': {'convergence': 1.2, 'quality': 1.4, 'diversity': 0.6},
            'ConstraintBias': {'convergence': 1.1, 'quality': 1.3, 'diversity': 1.0},
            'PreferenceBias': {'convergence': 1.0, 'quality': 1.2, 'diversity': 1.0}
        }

        return modifiers.get(bias_type, {'convergence': 1.0, 'quality': 1.0, 'diversity': 1.0})

    def _select_top_biases(self, predictions: Dict[str, Dict[str, float]],
                          optimization_goal: str, top_k: int) -> List[Tuple[str, float]]:
        """根据优化目标选择top_k偏置"""
        if optimization_goal == 'convergence':
            sorted_biases = sorted(predictions.items(),
                                key=lambda x: x[1]['convergence'], reverse=True)
        elif optimization_goal == 'quality':
            sorted_biases = sorted(predictions.items(),
                                key=lambda x: x[1]['quality'], reverse=True)
        else:  # balanced
            sorted_biases = sorted(predictions.items(),
                                key=lambda x: x[1]['overall'], reverse=True)

        return sorted_biases[:top_k]

    def _compute_bias_weights(self, selected_biases: List[Tuple[str, float]]) -> Dict[str, float]:
        """计算偏置权重"""
        if not selected_biases:
            return {}

        # 标准化权重
        scores = [score for _, score in selected_biases]
        max_score = max(scores) if scores else 1.0

        weights = {}
        for bias_name, score in selected_biases:
            # 将预测分数转换为0.05-0.3的权重范围
            normalized_score = score / max_score if max_score > 0 else 0
            weight = 0.05 + normalized_score * 0.25
            weights[bias_name] = weight

        return weights

    def _generate_reasoning(self, problem_features: ProblemFeatures,
                          algorithmic_biases: List[Tuple[str, float]],
                          domain_biases: List[Tuple[str, float]],
                          optimization_goal: str) -> List[str]:
        """生成推荐理由"""
        reasoning = []

        # 问题特征分析
        if problem_features.dimension > 50:
            reasoning.append("High-dimensional problem: selected biases for curse of dimensionality mitigation")

        if problem_features.num_objectives > 1:
            reasoning.append("Multi-objective problem: biases focus on Pareto front convergence")

        if problem_features.constraint_count > 0:
            reasoning.append("Constrained problem: constraint handling biases prioritized")

        # 偏置类型分析
        algorithmic_types = [b[0] for b in algorithmic_biases]
        domain_types = [b[0] for b in domain_biases]

        if 'DiversityBias' in algorithmic_types:
            reasoning.append("Diversity bias included to prevent premature convergence")

        if 'ConvergenceBias' in algorithmic_types:
            reasoning.append("Convergence bias included to accelerate optimization")

        # 优化目标分析
        if optimization_goal == 'convergence':
            reasoning.append("Optimization for fast convergence")
        elif optimization_goal == 'quality':
            reasoning.append("Optimization for high solution quality")
        else:
            reasoning.append("Balanced optimization approach")

        return reasoning

    def _compute_confidence(self, algo_predictions: Dict, domain_predictions: Dict,
                          problem_features: ProblemFeatures) -> float:
        """计算推荐置信度"""
        # 基于预测一致性计算置信度
        algo_scores = [p['overall'] for p in algo_predictions.values()]
        domain_scores = [p['overall'] for p in domain_predictions.values()]

        # 计算预测方差
        algo_var = np.var(algo_scores) if algo_scores else 0
        domain_var = np.var(domain_scores) if domain_scores else 0

        # 方差越小，置信度越高
        confidence = 1.0 / (1.0 + algo_var + domain_var)

        # 考虑问题与历史数据的相似性
        similarity = self._compute_problem_similarity(problem_features)
        confidence *= similarity

        return min(max(confidence, 0.0), 1.0)

    def _compute_problem_similarity(self, problem_features: ProblemFeatures) -> float:
        """计算问题与历史数据的相似性"""
        if len(self.problem_database) == 0:
            return 0.5  # 默认相似度

        current_features = np.array(self._extract_feature_vector(problem_features))

        similarities = []
        for problem_data in self.problem_database:
            historical_features = np.array(
                self._extract_feature_vector(problem_data['features']))

            # 计算余弦相似度
            similarity = np.dot(current_features, historical_features) / (
                np.linalg.norm(current_features) * np.linalg.norm(historical_features) + 1e-8)
            similarities.append(similarity)

        return max(similarities) if similarities else 0.5

    def _estimate_expected_improvement(self, selected_algo: List, selected_domain: List,
                                     algo_predictions: Dict, domain_predictions: Dict) -> float:
        """估计预期改进"""
        total_improvement = 0.0
        count = 0

        for bias_name, _ in selected_algo:
            if bias_name in algo_predictions:
                total_improvement += algo_predictions[bias_name]['overall']
                count += 1

        for bias_name, _ in selected_domain:
            if bias_name in domain_predictions:
                total_improvement += domain_predictions[bias_name]['overall']
                count += 1

        return total_improvement / count if count > 0 else 0.0

    def _generate_alternatives(self, algo_predictions: Dict, domain_predictions: Dict,
                             optimization_goal: str, top_k: int) -> List[Dict]:
        """生成备选方案"""
        alternatives = []

        # 方案1：侧重不同优化目标
        for goal in ['convergence', 'quality']:
            if goal != optimization_goal:
                algo_selected = self._select_top_biases(algo_predictions, goal, top_k)
                domain_selected = self._select_top_biases(domain_predictions, goal, top_k // 2)

                alternative = {
                    'description': f"Alternative focused on {goal}",
                    'algorithmic_biases': self._compute_bias_weights(algo_selected),
                    'domain_biases': self._compute_bias_weights(domain_selected),
                    'expected_improvement': self._estimate_expected_improvement(
                        algo_selected, domain_selected, algo_predictions, domain_predictions)
                }
                alternatives.append(alternative)

        # 方案2：保守方案（选择中等效果的偏置）
        conservative_algo = sorted(algo_predictions.items(),
                                 key=lambda x: abs(x[1]['overall'] - np.median([p['overall'] for p in algo_predictions.values()])))[:top_k]
        conservative_domain = sorted(domain_predictions.items(),
                                   key=lambda x: abs(x[1]['overall'] - np.median([p['overall'] for p in domain_predictions.values()])))[:top_k // 2]

        alternative = {
            'description': "Conservative balanced approach",
            'algorithmic_biases': self._compute_bias_weights(conservative_algo),
            'domain_biases': self._compute_bias_weights(conservative_domain),
            'expected_improvement': self._estimate_expected_improvement(
                conservative_algo, conservative_domain, algo_predictions, domain_predictions)
        }
        alternatives.append(alternative)

        return alternatives

    def _heuristic_recommendation(self, problem_features: ProblemFeatures,
                                optimization_goal: str, top_k: int) -> BiasRecommendation:
        """启发式推荐（当没有训练模型时）"""
        # 基于规则的启发式推荐
        algorithmic_biases = {}
        domain_biases = {}

        # 根据问题特征推荐偏置
        if problem_features.dimension > 50:
            algorithmic_biases['DiversityBias'] = 0.2
            algorithmic_biases['PopulationDensityBias'] = 0.15

        if problem_features.num_objectives > 1:
            algorithmic_biases['ConvergenceBias'] = 0.1
            algorithmic_biases['PrecisionBias'] = 0.1

        if problem_features.constraint_count > 0:
            domain_biases['ConstraintBias'] = 0.3

        if optimization_goal == 'convergence':
            algorithmic_biases['ConvergenceBias'] = 0.25
        elif optimization_goal == 'quality':
            algorithmic_biases['PrecisionBias'] = 0.2

        reasoning = [
            "Heuristic recommendation based on problem characteristics",
            f"Problem type: {problem_features.problem_type}",
            f"Optimization goal: {optimization_goal}"
        ]

        return BiasRecommendation(
            algorithmic_biases=algorithmic_biases,
            domain_biases=domain_biases,
            confidence_score=0.5,
            expected_improvement=10.0,
            reasoning=reasoning,
            alternative_suggestions=[]
        )

    def _get_best_bias_metrics_for_problem(self, problem_id: str) -> Optional[BiasEffectivenessMetrics]:
        """获取特定问题的最佳偏置效果"""
        best_metrics = None
        best_score = -float('inf')

        for bias_name, metrics_list in self.bias_performance_db.items():
            for metrics in metrics_list:
                score = self._compute_overall_score(metrics)
                if score > best_score:
                    best_score = score
                    best_metrics = metrics

        return best_metrics

    def _compute_overall_score(self, metrics: BiasEffectivenessMetrics) -> float:
        """计算综合得分"""
        # 简化的综合得分计算
        weights = {
            'convergence': 0.3,
            'quality': 0.4,
            'diversity': 0.2,
            'robustness': 0.1
        }

        score = (weights['convergence'] * min(max(metrics.convergence_improvement / 100, 0), 1) +
                weights['quality'] * min(max(metrics.solution_quality_boost / 100, 0), 1) +
                weights['diversity'] * metrics.diversity_score +
                weights['robustness'] * metrics.robustness_score)

        # 减去开销惩罚
        overhead_penalty = min(metrics.computational_overhead / 100, 0.1)
        score = max(score - overhead_penalty, 0)

        return score * 100

    def _models_trained(self) -> bool:
        """检查模型是否已训练"""
        try:
            # 简单检查：尝试加载模型
            joblib.load(f"{self.model_save_path}_rf.pkl")
            joblib.load(f"{self.model_save_path}_gb.pkl")
            joblib.load(f"{self.model_save_path}_nn.pkl")
            return True
        except:
            return False

    def _save_models(self):
        """保存训练好的模型"""
        try:
            joblib.dump(self.models['random_forest'], f"{self.model_save_path}_rf.pkl")
            joblib.dump(self.models['gradient_boost'], f"{self.model_save_path}_gb.pkl")
            joblib.dump(self.models['neural_network'], f"{self.model_save_path}_nn.pkl")
            joblib.dump(self.scaler, f"{self.model_save_path}_scaler.pkl")
            self.logger.info("Models saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving models: {e}")

    def load_models(self) -> bool:
        """加载训练好的模型"""
        try:
            self.models['random_forest'] = joblib.load(f"{self.model_save_path}_rf.pkl")
            self.models['gradient_boost'] = joblib.load(f"{self.model_save_path}_gb.pkl")
            self.models['neural_network'] = joblib.load(f"{self.model_save_path}_nn.pkl")
            self.scaler = joblib.load(f"{self.model_save_path}_scaler.pkl")
            self.logger.info("Models loaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
            return False

    def export_database(self, filename: str):
        """导出历史数据库"""
        export_data = {
            'problems': [],
            'bias_performance': {}
        }

        # 导出问题数据
        for problem_data in self.problem_database:
            features = problem_data['features']
            export_data['problems'].append({
                'problem_id': features.problem_id,
                'problem_type': features.problem_type,
                'dimension': features.dimension,
                'num_objectives': features.num_objectives,
                'constraint_count': features.constraint_count,
                'multimodality': features.multimodality,
                'separability': features.separability,
                'ruggedness': features.ruggedness,
                'landscape_noise': features.landscape_noise,
                'search_space_size': features.search_space_size,
                'constraint_density': features.constraint_density,
                'feasible_region_ratio': features.feasible_region_ratio,
                'evaluation_cost': features.evaluation_cost,
                'max_evaluations': features.max_evaluations
            })

        # 导出偏置效果数据
        for bias_name, metrics_list in self.bias_performance_db.items():
            export_data['bias_performance'][bias_name] = [
                {
                    'convergence_improvement': m.convergence_improvement,
                    'solution_quality_boost': m.solution_quality_boost,
                    'diversity_score': m.diversity_score,
                    'computational_overhead': m.computational_overhead,
                    'robustness_score': m.robustness_score,
                    'consistency_score': m.consistency_score,
                    'overall_score': self._compute_overall_score(m)
                }
                for m in metrics_list
            ]

        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)

        self.logger.info(f"Database exported to {filename}")

    def import_database(self, filename: str):
        """导入历史数据库"""
        try:
            with open(filename, 'r') as f:
                import_data = json.load(f)

            # 导入问题数据
            for problem_data in import_data['problems']:
                features = ProblemFeatures(**problem_data)
                self.problem_database.append({'features': features})

            # 导入偏置效果数据
            for bias_name, metrics_data in import_data['bias_performance'].items():
                for metric_data in metrics_data:
                    metrics = BiasEffectivenessMetrics(
                        bias_name=bias_name,
                        bias_type='algorithmic',  # 默认类型
                        convergence_improvement=metric_data['convergence_improvement'],
                        solution_quality_boost=metric_data['solution_quality_boost'],
                        diversity_score=metric_data['diversity_score'],
                        computational_overhead=metric_data['computational_overhead'],
                        robustness_score=metric_data['robustness_score'],
                        consistency_score=metric_data['consistency_score']
                    )
                    self.bias_performance_db[bias_name].append(metrics)

            self.logger.info(f"Database imported from {filename}")

        except Exception as e:
            self.logger.error(f"Error importing database: {e}")