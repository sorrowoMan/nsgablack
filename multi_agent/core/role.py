"""
智能体角色系统

定义不同的智能体角色及其特性
"""

from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import inspect


class AgentRole(Enum):
    """智能体角色枚举"""
    EXPLORER = "explorer"          # 探索者：发现新区域
    EXPLOITER = "exploiter"        # 开发者：深入优化
    WAITER = "waiter"              # 等待者：学习模式
    COORDINATOR = "coordinator"    # 协调者：全局策略
    ADVISOR = "advisor"            # 建议者：智能建议

    # 可以扩展的角色
    SCOUT = "scout"                # 侦察者：快速扫描
    HARVESTER = "harvester"        # 收割者：收集优质解
    GUARDIAN = "guardian"          # 守护者：保持多样性
    INNOVATOR = "innovator"        # 创新者：产生新颖解

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"AgentRole.{self.name}"


@dataclass
class RoleCharacteristics:
    """角色特性定义"""
    exploration_rate: float          # 探索倾向 (0-1)
    exploitation_rate: float        # 开发倾向 (0-1)
    learning_rate: float            # 学习能力 (0-1)
    communication_rate: float       # 交流频率 (0-1)
    risk_tolerance: float           # 风险容忍度 (0-1)
    diversity_weight: float         # 多样性权重
    constraint_tolerance: float     # 约束容忍度
    mutation_intensity: float       # 变异强度
    selection_pressure: float       # 选择压力

    def __post_init__(self):
        """确保参数在合理范围内"""
        for field_name, value in self.__dict__.items():
            if isinstance(value, (int, float)):
                setattr(self, field_name, max(0.0, min(1.0, value)))


class RoleRegistry:
    """角色注册表"""

    _registry = {}
    _characteristics = {}

    @classmethod
    def register_role(cls, role: AgentRole, characteristics: RoleCharacteristics):
        """注册角色特性"""
        cls._characteristics[role] = characteristics

    @classmethod
    def get_characteristics(cls, role: AgentRole) -> Optional[RoleCharacteristics]:
        """获取角色特性"""
        return cls._characteristics.get(role)

    @classmethod
    def get_all_roles(cls) -> List[AgentRole]:
        """获取所有注册的角色"""
        return list(cls._characteristics.keys())

    @classmethod
    def register_custom_role(cls, name: str, characteristics: RoleCharacteristics):
        """注册自定义角色"""
        # 创建新的角色枚举值
        # 注意：这里简化处理，实际可能需要更复杂的动态枚举创建
        custom_role = AgentRole(name)
        cls.register_role(custom_role, characteristics)
        return custom_role


# 预定义的角色特性
DEFAULT_ROLE_CHARACTERISTICS = {
    AgentRole.EXPLORER: RoleCharacteristics(
        exploration_rate=0.9,
        exploitation_rate=0.2,
        learning_rate=0.3,
        communication_rate=0.7,
        risk_tolerance=0.8,
        diversity_weight=2.0,
        constraint_tolerance=0.6,
        mutation_intensity=0.3,
        selection_pressure=0.3
    ),

    AgentRole.EXPLOITER: RoleCharacteristics(
        exploration_rate=0.1,
        exploitation_rate=0.9,
        learning_rate=0.5,
        communication_rate=0.5,
        risk_tolerance=0.2,
        diversity_weight=0.3,
        constraint_tolerance=0.2,
        mutation_intensity=0.1,
        selection_pressure=0.8
    ),

    AgentRole.WAITER: RoleCharacteristics(
        exploration_rate=0.1,
        exploitation_rate=0.3,
        learning_rate=0.9,
        communication_rate=0.9,
        risk_tolerance=0.3,
        diversity_weight=1.0,
        constraint_tolerance=0.4,
        mutation_intensity=0.05,
        selection_pressure=0.5
    ),

    AgentRole.COORDINATOR: RoleCharacteristics(
        exploration_rate=0.4,
        exploitation_rate=0.6,
        learning_rate=0.7,
        communication_rate=0.8,
        risk_tolerance=0.5,
        diversity_weight=1.5,
        constraint_tolerance=0.5,
        mutation_intensity=0.2,
        selection_pressure=0.6
    ),

    # 扩展角色
    AgentRole.SCOUT: RoleCharacteristics(
        exploration_rate=1.0,
        exploitation_rate=0.0,
        learning_rate=0.2,
        communication_rate=0.8,
        risk_tolerance=1.0,
        diversity_weight=3.0,
        constraint_tolerance=0.8,
        mutation_intensity=0.5,
        selection_pressure=0.1
    ),

    AgentRole.HARVESTER: RoleCharacteristics(
        exploration_rate=0.0,
        exploitation_rate=1.0,
        learning_rate=0.3,
        communication_rate=0.3,
        risk_tolerance=0.1,
        diversity_weight=0.1,
        constraint_tolerance=0.1,
        mutation_intensity=0.02,
        selection_pressure=0.9
    ),

    AgentRole.GUARDIAN: RoleCharacteristics(
        exploration_rate=0.5,
        exploitation_rate=0.3,
        learning_rate=0.4,
        communication_rate=0.6,
        risk_tolerance=0.6,
        diversity_weight=2.5,
        constraint_tolerance=0.5,
        mutation_intensity=0.2,
        selection_pressure=0.4
    ),

    AgentRole.INNOVATOR: RoleCharacteristics(
        exploration_rate=0.7,
        exploitation_rate=0.2,
        learning_rate=0.6,
        communication_rate=0.4,
        risk_tolerance=0.9,
        diversity_weight=3.5,
        constraint_tolerance=0.7,
        mutation_intensity=0.4,
        selection_pressure=0.2
    ),

    # 建议者 - 新增核心角色！
    AgentRole.ADVISOR: RoleCharacteristics(
        exploration_rate=0.5,
        exploitation_rate=0.5,
        learning_rate=0.95,           # 极高学习能力
        communication_rate=1.0,       # 极高交流频率（向其他智能提供建议）
        risk_tolerance=0.6,
        diversity_weight=1.2,
        constraint_tolerance=0.5,
        mutation_intensity=0.15,      # 较低变异（主要靠预测而非随机变异）
        selection_pressure=0.7
    )
}


# 初始化默认角色
def _initialize_default_roles():
    """初始化默认角色特性"""
    for role, characteristics in DEFAULT_ROLE_CHARACTERISTICS.items():
        RoleRegistry.register_role(role, characteristics)


# 自动初始化
_initialize_default_roles()


class RoleFactory:
    """角色工厂"""

    @staticmethod
    def create_role(role_type: AgentRole, **kwargs) -> RoleCharacteristics:
        """创建角色特性"""
        base_characteristics = RoleRegistry.get_characteristics(role_type)
        if base_characteristics is None:
            raise ValueError(f"未知角色类型: {role_type}")

        # 应用自定义参数
        characteristics = RoleCharacteristics(**base_characteristics.__dict__)
        for key, value in kwargs.items():
            if hasattr(characteristics, key):
                setattr(characteristics, key, value)

        return characteristics

    @staticmethod
    def create_hybrid_role(roles: List[AgentRole], weights: List[float] = None) -> RoleCharacteristics:
        """创建混合角色"""
        if weights is None:
            weights = [1.0 / len(roles)] * len(roles)

        if len(roles) != len(weights):
            raise ValueError("角色数量和权重数量不匹配")

        # 归一化权重
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # 加权平均特性
        characteristics_list = [RoleRegistry.get_characteristics(role) for role in roles]
        if None in characteristics_list:
            raise ValueError("包含未知角色")

        hybrid_characteristics = {}
        for field_name in characteristics_list[0].__dataclass_fields__:
            weighted_value = sum(
                getattr(char, field_name) * weight
                for char, weight in zip(characteristics_list, weights)
            )
            hybrid_characteristics[field_name] = weighted_value

        return RoleCharacteristics(**hybrid_characteristics)


def get_role_description(role: AgentRole) -> str:
    """获取角色描述"""
    descriptions = {
        AgentRole.EXPLORER: "探索者：专注于发现新的搜索区域，保持高多样性",
        AgentRole.EXPLOITER: "开发者：深入优化已发现的优质区域，追求精度",
        AgentRole.WAITER: "等待者：学习其他智能体的成功模式，进行知识整合",
        AgentRole.COORDINATOR: "协调者：平衡全局策略，调整智能体行为",
        AgentRole.ADVISOR: "建议者：分析解分布趋势，用贝叶斯/ML预测最优区域，向其他智能体提供建议",
        AgentRole.SCOUT: "侦察者：快速扫描整个搜索空间，发现潜在机会",
        AgentRole.HARVESTER: "收割者：高效收集和优化已知的优质解",
        AgentRole.GUARDIAN: "守护者：维护种群多样性，防止过早收敛",
        AgentRole.INNOVATOR: "创新者：产生新颖的解，突破局部最优"
    }
    return descriptions.get(role, f"{role.value}：自定义角色")


def suggest_role_config(problem_type: str) -> List[AgentRole]:
    """根据问题类型推荐角色配置"""
    suggestions = {
        'single_objective': [AgentRole.EXPLORER, AgentRole.EXPLOITER, AgentRole.COORDINATOR],
        'multi_objective': [AgentRole.EXPLORER, AgentRole.EXPLOITER, AgentRole.WAITER, AgentRole.COORDINATOR],
        'constrained': [AgentRole.EXPLORER, AgentRole.EXPLOITER, AgentRole.GUARDIAN],
        'dynamic': [AgentRole.SCOUT, AgentRole.EXPLOITER, AgentRole.INNOVATOR, AgentRole.COORDINATOR],
        'large_scale': [AgentRole.SCOUT, AgentRole.HARVESTER, AgentRole.COORDINATOR],
        'rugged_landscape': [AgentRole.EXPLORER, AgentRole.INNOVATOR, AgentRole.GUARDIAN]
    }
    return suggestions.get(problem_type.lower(), list(AgentRole)[:4])