# -*- coding: utf-8 -*-
"""
角色偏置组合配置

定义每个角色的偏置组合策略
通过组合不同的算法偏置，实现角色的差异化行为

设计理念：
- 所有角色使用统一的 NSGA-II 搜索引擎
- 通过偏置系统注入其他算法的优点
- 角色差异体现在偏置组合的不同
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from multi_agent.core.role import AgentRole

# 导入各种算法偏置
# 从 bias 模块导入
try:
    from bias.algorithmic.nsga2 import NSGA2Bias
    from bias.algorithmic.simulated_annealing import SimulatedAnnealingBias
    from bias.algorithmic.differential_evolution import DifferentialEvolutionBias
    from bias.algorithmic.pattern_search import PatternSearchBias
    from bias.algorithmic.gradient_descent import GradientDescentBias
    # from bias.algorithmic.diversity import DiversityBias
    # from bias.algorithmic.convergence import ConvergenceBias
    BIAS_AVAILABLE = True
except ImportError:
    BIAS_AVAILABLE = False
    print("[WARN] 无法导入算法偏置模块，将使用简化配置")


@dataclass
class BiasConfig:
    """偏置配置项"""
    bias_class: type                 # 偏置类
    params: Dict[str, Any]            # 初始化参数
    weight: float                    # 权重（控制该偏置的影响程度）
    name: str                        # 偏置名称（用于日志和调试）


class RoleBiasCombinationManager:
    """
    角色偏置组合管理器

    负责配置和管理每个角色的偏置组合策略
    每个角色都有自己的"偏置鸡尾酒"（多种偏置的组合）
    """

    def __init__(self):
        """初始化偏置组合管理器"""
        # 存储每个角色的偏置配置
        self.role_bias_configs: Dict[AgentRole, List[BiasConfig]] = {}

        # 配置默认的偏置组合
        self._setup_default_combinations()

    def _setup_default_combinations(self):
        """
        设置默认的偏置组合配置

        核心理念：
        - Explorer: NSGA-II + SA全局搜索 + 多样性增强
        - Exploiter: NSGA-II + 梯度快速收敛 + 收敛强调
        - Waiter: NSGA-II + 学习偏置 + 模式跟随
        - Advisor: NSGA-II + 贝叶斯智能引导 + 分析偏置
        - Coordinator: NSGA-II + 自适应调整 + 平衡
        """

        if not BIAS_AVAILABLE:
            # 偏置模块不可用，使用简化配置
            print("[INFO] 使用简化的偏置配置")
            return

        # ========== Explorer（探索者）偏置组合 ==========
        self.role_bias_configs[AgentRole.EXPLORER] = [
            # 1. NSGA-II 偏置（强调多样性）
            BiasConfig(
                bias_class=NSGA2Bias,
                params={
                    'initial_weight': 0.1,
                    'rank_weight': 0.3,        # 降低 rank 权重
                    'crowding_weight': 0.7    # 强调拥挤距离（多样性）
                },
                weight=1.0,                  # NSGA-II 是基础，高权重
                name='nsga2_diversity'
            ),

            # 2. 模拟退火偏置（全局搜索能力）
            BiasConfig(
                bias_class=SimulatedAnnealingBias,
                params={
                    'initial_weight': 0.15,
                    'initial_temperature': 100.0,
                    'cooling_rate': 0.99      # 缓慢冷却，保持探索
                },
                weight=0.5,                  # SA 的全局搜索能力
                name='sa_global_search'
            ),

            # 3. 差分进化偏置（探索能力）
            BiasConfig(
                bias_class=DifferentialEvolutionBias,
                params={
                    'initial_weight': 0.1,
                    'F': 0.8,                 # 标准DE推荐值
                    'strategy': 'rand'        # 随机策略，更多探索
                },
                weight=0.3,                  # DE 的全局探索
                name='de_exploration'
            )

            # TODO: 添加多样性增强偏置
            # BiasConfig(
            #     bias_class=DiversityBias,
            #     params={'weight': 0.2},
            #     weight=0.8,
            #     name='diversity_enhancement'
            # )
        ]

        # ========== Exploiter（开发者）偏置组合 ==========
        self.role_bias_configs[AgentRole.EXPLOITER] = [
            # 1. NSGA-II 偏置（强调收敛）
            BiasConfig(
                bias_class=NSGA2Bias,
                params={
                    'initial_weight': 0.1,
                    'rank_weight': 0.7,        # 强调 rank（收敛）
                    'crowding_weight': 0.3    # 降低拥挤权重
                },
                weight=1.0,                  # NSGA-II 基础
                name='nsga2_convergence'
            ),

            # 2. 模式搜索偏置（局部精化）
            BiasConfig(
                bias_class=PatternSearchBias,
                params={
                    'initial_weight': 0.1,
                    'step_size': 0.1,         # 局部搜索步长
                    'pattern_size': 2         # 模式大小
                },
                weight=0.6,                  # PS 的局部精化能力
                name='ps_local_refinement'
            ),

            # 3. 梯度下降偏置（快速收敛）
            BiasConfig(
                bias_class=GradientDescentBias,
                params={
                    'initial_weight': 0.1,
                    'learning_rate': 0.1,     # 学习率
                    'epsilon': 1e-5           # 有限差分步长
                },
                weight=0.5,                  # GD 的快速收敛
                name='gd_fast_convergence'
            )

            # TODO: 添加收敛偏置
            # BiasConfig(
            #     bias_class=ConvergenceBias,
            #     params={'weight': 0.2},
            #     weight=0.9,
            #     name='convergence_focus'
            # )
        ]

        # ========== Waiter（等待者）偏置组合 ==========
        self.role_bias_configs[AgentRole.WAITER] = [
            # 1. NSGA-II 偏置（平衡）
            BiasConfig(
                bias_class=NSGA2Bias,
                params={
                    'initial_weight': 0.1,
                    'rank_weight': 0.5,
                    'crowding_weight': 0.5
                },
                weight=1.0,
                name='nsga2_balanced'
            )

            # TODO: 添加学习偏置
            # BiasConfig(
            #     bias_class=LearningBias,
            #     params={'weight': 0.2},
            #     weight=0.7,
            #     name='pattern_learning'
            # )
        ]

        # ========== Advisor（建议者）偏置组合 ==========
        self.role_bias_configs[AgentRole.ADVISOR] = [
            # 1. NSGA-II 偏置（平衡）
            BiasConfig(
                bias_class=NSGA2Bias,
                params={
                    'initial_weight': 0.1,
                    'rank_weight': 0.5,
                    'crowding_weight': 0.5
                },
                weight=1.0,
                name='nsga2_balanced'
            )

            # TODO: 添加贝叶斯偏置（智能引导）
            # BiasConfig(
            #     bias_class=BayesianBias,
            #     params={'weight': 0.4},
            #     weight=0.7,
            #     name='bayesian_guidance'
            # )

            # TODO: 添加分析偏置
            # BiasConfig(
            #     bias_class=AnalyticalBias,
            #     params={'weight': 0.3},
            #     weight=0.8,
            #     name='analytical_insight'
            # )
        ]

        # ========== Coordinator（协调者）偏置组合 ==========
        self.role_bias_configs[AgentRole.COORDINATOR] = [
            # 1. NSGA-II 偏置（自适应）
            BiasConfig(
                bias_class=NSGA2Bias,
                params={
                    'initial_weight': 0.1,
                    'rank_weight': 0.5,
                    'crowding_weight': 0.5
                },
                weight=1.0,
                name='nsga2_adaptive'
            )

            # TODO: 添加自适应偏置
            # BiasConfig(
            #     bias_class=AdaptiveBias,
            #     params={'weight': 0.3},
            #     weight=0.8,
            #     name='adaptive_balance'
            # )
        ]

    def get_role_bias_configs(self, role: AgentRole) -> List[BiasConfig]:
        """
        获取角色的偏置配置列表

        Args:
            role: 智能体角色

        Returns:
            该角色的偏置配置列表
        """
        return self.role_bias_configs.get(role, [])

    def create_role_bias_instances(self, role: AgentRole) -> List[Any]:
        """
        为指定角色创建偏置实例列表

        Args:
            role: 智能体角色

        Returns:
            偏置实例列表（已初始化）
        """
        configs = self.get_role_bias_configs(role)
        instances = []

        for config in configs:
            try:
                # 创建偏置实例
                bias_instance = config.bias_class(**config.params)
                instances.append({
                    'bias': bias_instance,
                    'weight': config.weight,
                    'name': config.name
                })
            except Exception as e:
                print(f"[WARN] 无法创建偏置 {config.name}: {e}")

        return instances

    def add_custom_bias(
        self,
        role: AgentRole,
        bias_class: type,
        params: Dict[str, Any],
        weight: float,
        name: str
    ):
        """
        为指定角色添加自定义偏置

        Args:
            role: 智能体角色
            bias_class: 偏置类
            params: 初始化参数
            weight: 权重
            name: 偏置名称
        """
        if role not in self.role_bias_configs:
            self.role_bias_configs[role] = []

        config = BiasConfig(
            bias_class=bias_class,
            params=params,
            weight=weight,
            name=name
        )

        self.role_bias_configs[role].append(config)

    def remove_bias(self, role: AgentRole, bias_name: str):
        """
        从角色的偏置组合中移除指定偏置

        Args:
            role: 智能体角色
            bias_name: 偏置名称
        """
        if role in self.role_bias_configs:
            self.role_bias_configs[role] = [
                config for config in self.role_bias_configs[role]
                if config.name != bias_name
            ]

    def get_bias_combination_description(self, role: AgentRole) -> str:
        """
        获取角色偏置组合的文字描述

        Args:
            role: 智能体角色

        Returns:
            偏置组合的描述
        """
        configs = self.get_role_bias_configs(role)

        if not configs:
            return f"{role.value}: 无偏置配置"

        description = f"{role.value} 的偏置组合:\n"

        for i, config in enumerate(configs, 1):
            description += f"  {i}. {config.name} (权重: {config.weight})\n"

        return description


# ========== 便捷函数 ==========

def get_default_bias_combinations() -> RoleBiasCombinationManager:
    """
    获取默认的角色偏置组合管理器

    Returns:
        配置好的偏置组合管理器
    """
    return RoleBiasCombinationManager()


def create_role_bias_profiles() -> Dict[AgentRole, Dict[str, Any]]:
    """
    创建角色偏置配置字典（兼容旧接口）

    Returns:
        角色到偏置配置的映射
    """
    manager = get_default_bias_combinations()

    profiles = {}

    for role in AgentRole:
        instances = manager.create_role_bias_instances(role)
        profiles[role] = {
            'biases': [inst['bias'] for inst in instances],
            'weights': [inst['weight'] for inst in instances],
            'names': [inst['name'] for inst in instances]
        }

    return profiles
