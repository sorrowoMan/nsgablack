"""
偏置配置文件

定义各种偏置配置和参数
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import numpy as np


@dataclass
class BiasProfile:
    """偏置配置文件"""
    name: str
    parameters: Dict[str, float] = field(default_factory=dict)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    objectives: List[Dict[str, str]] = field(default_factory=list)
    description: str = ""

    def get_parameter(self, key: str, default: float = 0.0) -> float:
        """获取参数值"""
        return self.parameters.get(key, default)

    def set_parameter(self, key: str, value: float):
        """设置参数值"""
        self.parameters[key] = value

    def apply_constraints(self):
        """应用约束条件"""
        for constraint in self.constraints:
            param = constraint.get('parameter')
            if param in self.parameters:
                value = self.parameters[param]
                min_val = constraint.get('min', -np.inf)
                max_val = constraint.get('max', np.inf)
                self.parameters[param] = np.clip(value, min_val, max_val)

    def evaluate_objectives(self) -> Dict[str, float]:
        """评估目标达成情况"""
        results = {}
        for obj in self.objectives:
            param = obj.get('parameter')
            target = obj.get('target')
            if param in self.parameters:
                value = self.parameters[param]
                if target == 'maximize':
                    results[param] = value
                elif target == 'minimize':
                    results[param] = -value
                elif target == 'moderate':
                    # 偏向中间值
                    ideal = 0.5
                    results[param] = -abs(value - ideal)
        return results

    def copy(self) -> 'BiasProfile':
        """复制偏置配置"""
        return BiasProfile(
            name=self.name + "_copy",
            parameters=self.parameters.copy(),
            constraints=self.constraints.copy(),
            objectives=self.objectives.copy(),
            description=self.description
        )


@dataclass
class DynamicBiasProfile(BiasProfile):
    """动态偏置配置"""
    adaptation_rate: float = 0.1
    learning_rate: float = 0.05
    performance_history: List[Dict] = field(default_factory=list)
    current_stage: str = "early"

    def update_from_feedback(self, feedback: Dict, iteration: int):
        """
        根据反馈更新偏置参数

        Args:
            feedback: 反馈信息字典
            iteration: 当前迭代次数
        """
        if not feedback:
            return

        # 计算性能指标
        performance_improvement = feedback.get('performance_improvement', 0)
        diversity_maintained = feedback.get('diversity', 0)
        constraint_satisfaction = feedback.get('constraint_satisfaction', 1)

        # 综合评分
        score = (performance_improvement * 0.4 +
                diversity_maintained * 0.3 +
                constraint_satisfaction * 0.3)

        self.performance_history.append({
            'iteration': iteration,
            'score': score,
            'feedback': feedback.copy()
        })

        # 更新学习率
        if len(self.performance_history) > 1:
            recent_improvement = score - self.performance_history[-2]['score']
            if recent_improvement > 0:
                self.learning_rate = min(self.learning_rate * 1.1, 0.5)
            else:
                self.learning_rate = max(self.learning_rate * 0.9, 0.01)

        # 自适应调整参数
        self._adapt_parameters(score, recent_improvement if len(self.performance_history) > 1 else 0)

    def _adapt_parameters(self, score: float, improvement: float):
        """自适应调整参数"""
        for param in self.parameters:
            if param in ['diversity_weight', 'exploration_rate']:
                # 根据性能调整探索相关参数
                if improvement < 0 and score < 0.5:  # 性能下降，需要更多探索
                    self.parameters[param] += self.learning_rate * 0.1
                else:
                    self.parameters[param] -= self.learning_rate * 0.05

            elif param in ['selection_pressure', 'mutation_rate']:
                # 根据多样性调整开发相关参数
                if score > 0.7:  # 性能好，增加开发压力
                    self.parameters[param] += self.learning_rate * 0.05
                else:
                    self.parameters[param] -= self.learning_rate * 0.05

        # 应用约束
        self.apply_constraints()

    def adapt_for_stage(self, optimization_stage: str):
        """根据优化阶段调整偏置"""
        stage_adjustments = {
            'early': {
                'exploration_rate': 1.2,
                'diversity_weight': 1.5,
                'mutation_rate': 1.3,
                'risk_tolerance': 1.2
            },
            'middle': {
                'exploration_rate': 1.0,
                'diversity_weight': 1.0,
                'mutation_rate': 1.0,
                'risk_tolerance': 1.0
            },
            'late': {
                'exploration_rate': 0.7,
                'diversity_weight': 0.8,
                'mutation_rate': 0.8,
                'risk_tolerance': 0.8
            }
        }

        if optimization_stage in stage_adjustments:
            adjustments = stage_adjustments[optimization_stage]
            for param, factor in adjustments.items():
                if param in self.parameters:
                    self.parameters[param] *= factor
                    self.parameters[param] = np.clip(self.parameters[param], 0, 1)

            self.current_stage = optimization_stage


class BiasLibrary:
    """偏置库 - 预定义偏置配置"""

    _profiles = {}

    @classmethod
    def register_profile(cls, name: str, profile: BiasProfile):
        """注册偏置配置"""
        cls._profiles[name] = profile

    @classmethod
    def get_profile(cls, name: str) -> Optional[BiasProfile]:
        """获取偏置配置"""
        return cls._profiles.get(name)

    @classmethod
    def list_profiles(cls) -> List[str]:
        """列出所有可用的偏置配置"""
        return list(cls._profiles.keys())

    @classmethod
    def get_profile_by_role(cls, role_name: str) -> Optional[BiasProfile]:
        """根据角色名称获取偏置配置"""
        profile_name = f"{role_name}_default"
        return cls.get_profile(profile_name)


# 预定义偏置配置
def _initialize_default_profiles():
    """初始化默认偏置配置"""

    # 探索者偏置
    explorer_profile = BiasProfile(
        name="explorer_default",
        parameters={
            'diversity_weight': 2.0,
            'exploration_rate': 0.9,
            'mutation_rate': 0.3,
            'crossover_rate': 0.6,
            'selection_pressure': 0.3,
            'constraint_tolerance': 0.6,
            'risk_tolerance': 0.8
        },
        constraints=[
            {'parameter': 'exploration_rate', 'min': 0.7, 'max': 1.0},
            {'parameter': 'diversity_weight', 'min': 1.5, 'max': 3.0}
        ],
        objectives=[
            {'parameter': 'diversity_weight', 'target': 'maximize'},
            {'parameter': 'constraint_tolerance', 'target': 'moderate'}
        ],
        description="探索者偏置：强调多样性和新区域发现"
    )

    # 开发者偏置
    exploiter_profile = BiasProfile(
        name="exploiter_default",
        parameters={
            'diversity_weight': 0.3,
            'exploration_rate': 0.1,
            'mutation_rate': 0.1,
            'crossover_rate': 0.9,
            'selection_pressure': 0.8,
            'constraint_tolerance': 0.2,
            'risk_tolerance': 0.2
        },
        constraints=[
            {'parameter': 'exploration_rate', 'min': 0.0, 'max': 0.3},
            {'parameter': 'selection_pressure', 'min': 0.7, 'max': 1.0}
        ],
        objectives=[
            {'parameter': 'selection_pressure', 'target': 'maximize'},
            {'parameter': 'diversity_weight', 'target': 'minimize'}
        ],
        description="开发者偏置：专注于局部搜索和精度提升"
    )

    # 等待者偏置
    waiter_profile = BiasProfile(
        name="waiter_default",
        parameters={
            'diversity_weight': 1.0,
            'exploration_rate': 0.1,
            'mutation_rate': 0.05,
            'crossover_rate': 0.7,
            'selection_pressure': 0.5,
            'constraint_tolerance': 0.4,
            'learning_rate': 0.8,
            'communication_rate': 0.9
        },
        constraints=[
            {'parameter': 'learning_rate', 'min': 0.5, 'max': 1.0}
        ],
        objectives=[
            {'parameter': 'learning_rate', 'target': 'maximize'}
        ],
        description="等待者偏置：专注于学习和知识整合"
    )

    # 协调者偏置
    coordinator_profile = BiasProfile(
        name="coordinator_default",
        parameters={
            'diversity_weight': 1.5,
            'exploration_rate': 0.4,
            'mutation_rate': 0.2,
            'crossover_rate': 0.8,
            'selection_pressure': 0.6,
            'constraint_tolerance': 0.5,
            'adaptation_rate': 0.7,
            'balancing_factor': 0.6
        },
        objectives=[
            {'parameter': 'balancing_factor', 'target': 'moderate'}
        ],
        description="协调者偏置：平衡探索与开发"
    )

    # 侦察者偏置
    scout_profile = BiasProfile(
        name="scout_default",
        parameters={
            'diversity_weight': 3.0,
            'exploration_rate': 1.0,
            'mutation_rate': 0.5,
            'crossover_rate': 0.4,
            'selection_pressure': 0.1,
            'constraint_tolerance': 0.8,
            'risk_tolerance': 1.0,
            'scanning_range': 0.9
        },
        description="侦察者偏置：超快速广域搜索"
    )

    # 创新者偏置
    innovator_profile = BiasProfile(
        name="innovator_default",
        parameters={
            'diversity_weight': 3.5,
            'exploration_rate': 0.7,
            'mutation_rate': 0.4,
            'crossover_rate': 0.5,
            'selection_pressure': 0.2,
            'constraint_tolerance': 0.7,
            'risk_tolerance': 0.9,
            'creativity_factor': 0.8
        },
        description="创新者偏置：产生突破性解决方案"
    )

    # 注册所有配置
    BiasLibrary.register_profile("explorer_default", explorer_profile)
    BiasLibrary.register_profile("exploiter_default", exploiter_profile)
    BiasLibrary.register_profile("waiter_default", waiter_profile)
    BiasLibrary.register_profile("coordinator_default", coordinator_profile)
    BiasLibrary.register_profile("scout_default", scout_profile)
    BiasLibrary.register_profile("innovator_default", innovator_profile)


# 初始化
_initialize_default_profiles()


def get_bias_profile(name: str) -> Optional[BiasProfile]:
    """获取偏置配置的便捷函数"""
    return BiasLibrary.get_profile(name)


def create_adaptive_profile(base_name: str, adaptation_config: Dict) -> DynamicBiasProfile:
    """创建自适应偏置配置"""
    base_profile = BiasLibrary.get_profile(base_name)
    if base_profile is None:
        raise ValueError(f"基础偏置配置 '{base_name}' 不存在")

    # 创建动态偏置
    dynamic_bias = DynamicBiasProfile(
        name=f"adaptive_{base_name}",
        parameters=base_profile.parameters.copy(),
        constraints=base_profile.constraints.copy(),
        objectives=base_profile.objectives.copy(),
        description=f"自适应版本: {base_profile.description}",
        **adaptation_config
    )

    return dynamic_bias


class BiasProfileFactory:
    """偏置配置工厂"""

    @staticmethod
    def create_for_problem_type(problem_type: str, complexity: str = 'medium') -> BiasProfile:
        """根据问题类型创建偏置配置"""
        profiles = {
            'single_objective': {
                'simple': 'exploiter_default',
                'medium': 'coordinator_default',
                'complex': 'explorer_default'
            },
            'multi_objective': {
                'simple': 'coordinator_default',
                'medium': 'explorer_default',
                'complex': 'waiter_default'
            },
            'constrained': {
                'simple': 'exploiter_default',
                'medium': 'coordinator_default',
                'complex': 'explorer_default'
            },
            'dynamic': {
                'simple': 'coordinator_default',
                'medium': 'explorer_default',
                'complex': 'waiter_default'
            }
        }

        profile_name = profiles.get(problem_type, {}).get(complexity, 'coordinator_default')
        return get_bias_profile(profile_name)

    @staticmethod
    def create_hybrid(profile_names: List[str], weights: List[float] = None) -> BiasProfile:
        """创建混合偏置配置"""
        if weights is None:
            weights = [1.0 / len(profile_names)] * len(profile_names)

        if len(profile_names) != len(weights):
            raise ValueError("配置名称数量和权重数量不匹配")

        # 获取基础配置
        base_profiles = [get_bias_profile(name) for name in profile_names]
        if None in base_profiles:
            raise ValueError("存在未知的偏置配置")

        # 加权平均参数
        hybrid_parameters = {}
        all_params = set()
        for profile in base_profiles:
            all_params.update(profile.parameters.keys())

        for param in all_params:
            weighted_value = 0
            for profile, weight in zip(base_profiles, weights):
                if param in profile.parameters:
                    weighted_value += profile.parameters[param] * weight
            hybrid_parameters[param] = weighted_value

        # 创建混合配置
        hybrid_profile = BiasProfile(
            name=f"hybrid_{'_'.join(profile_names)}",
            parameters=hybrid_parameters,
            constraints=[],  # 混合配置简化约束
            objectives=[]
        )

        return hybrid_profile