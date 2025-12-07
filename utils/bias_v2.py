"""
偏置模块 v2.0 - 双重架构实现
算法偏置 (Algorithmic Bias) + 业务偏置 (Domain Bias)

这个版本实现了可复用、可组合的偏置系统，将算法层面的优化引导与业务层面的约束和偏好分离。
"""

import numpy as np
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import json
from pathlib import Path


class OptimizationContext:
    """优化上下文信息"""

    def __init__(self, generation: int, individual: np.ndarray, population: List[np.ndarray] = None,
                 metrics: Dict[str, float] = None, history: List = None):
        self.generation = generation
        self.individual = individual
        self.population = population or []
        self.metrics = metrics or {}
        self.history = history or []
        self.is_stuck = False
        self.is_violating_constraints = False


class BaseBias(ABC):
    """偏置基类"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
        self.enabled = True

    @abstractmethod
    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算偏置值"""
        pass

    def enable(self):
        """启用偏置"""
        self.enabled = True

    def disable(self):
        """禁用偏置"""
        self.enabled = False

    def set_weight(self, weight: float):
        """设置权重"""
        self.weight = max(0.0, weight)


# ==================== 算法偏置模块 ====================

class AlgorithmicBias(BaseBias):
    """算法偏置基类"""
    pass


class DiversityBias(AlgorithmicBias):
    """多样性偏置：促进种群多样性"""

    def __init__(self, weight: float = 0.1, metric: str = 'euclidean'):
        super().__init__("diversity", weight)
        self.metric = metric

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.population:
            return 0.0

        # 计算与种群中其他个体的最小距离
        distances = []
        for other in context.population:
            if not np.array_equal(x, other):
                if self.metric == 'euclidean':
                    dist = np.linalg.norm(x - other)
                elif self.metric == 'manhattan':
                    dist = np.sum(np.abs(x - other))
                else:
                    dist = np.linalg.norm(x - other)
                distances.append(dist)

        if not distances:
            return 0.0

        min_distance = min(distances)
        # 距离越大，多样性贡献越大
        return self.weight * np.log(min_distance + 1.0)


class ConvergenceBias(AlgorithmicBias):
    """收敛性偏置：根据迭代阶段调整收敛倾向"""

    def __init__(self, weight: float = 0.1, early_gen: int = 10, late_gen: int = 50):
        super().__init__("convergence", weight)
        self.early_gen = early_gen
        self.late_gen = late_gen

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        gen = context.generation

        if gen < self.early_gen:
            # 早期：鼓励探索，不偏置收敛
            return 0.0
        elif gen < self.late_gen:
            # 中期：适度偏置收敛
            factor = (gen - self.early_gen) / (self.late_gen - self.early_gen)
            return self.weight * factor * 0.05
        else:
            # 后期：鼓励快速收敛
            return self.weight * 0.2


class ExplorationBias(AlgorithmicBias):
    """探索性偏置：避免早熟收敛"""

    def __init__(self, weight: float = 0.1, stagnation_threshold: int = 20):
        super().__init__("exploration", weight)
        self.stagnation_threshold = stagnation_threshold

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if len(context.history) < self.stagnation_threshold:
            return 0.0

        # 检查是否停滞
        recent_improvements = []
        for i in range(-self.stagnation_threshold, 0):
            if i < len(context.history):
                recent_improvements.append(context.history[i].get('improvement', 0))

        if len(recent_improvements) < self.stagnation_threshold:
            return 0.0

        avg_improvement = np.mean(recent_improvements)

        # 如果改进很小，增加探索偏置
        if avg_improvement < 1e-6:
            return self.weight * 0.3
        else:
            return self.weight * avg_improvement * 10


class PrecisionBias(AlgorithmicBias):
    """精度偏置：在好解周围精细搜索"""

    def __init__(self, weight: float = 0.1, precision_radius: float = 0.1):
        super().__init__("precision", weight)
        self.precision_radius = precision_radius
        self.known_good_solutions = []

    def add_good_solution(self, x: np.ndarray):
        """添加已知的好的解"""
        self.known_good_solutions.append(x.copy())

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not self.known_good_solutions:
            return 0.0

        # 计算到最近好解的距离
        min_distance = min(np.linalg.norm(x - good) for good in self.known_good_solutions)

        # 如果在精度范围内，给予奖励
        if min_distance < self.precision_radius:
            return -self.weight * min_distance  # 负值表示奖励
        else:
            return 0.0


# ==================== 业务偏置模块 ====================

class DomainBias(BaseBias):
    """业务偏置基类"""
    pass


class ConstraintBias(DomainBias):
    """约束偏置：处理业务约束"""

    def __init__(self, weight: float = 1.0):
        super().__init__("constraint", weight)
        self.hard_constraints = []
        self.soft_constraints = []
        self.preferred_constraints = []

    def add_hard_constraint(self, constraint_func):
        """添加硬约束"""
        self.hard_constraints.append(constraint_func)

    def add_soft_constraint(self, constraint_func):
        """添加软约束"""
        self.soft_constraints.append(constraint_func)

    def add_preferred_constraint(self, constraint_func):
        """添加偏好约束"""
        self.preferred_constraints.append(constraint_func)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        bias = 0.0

        # 硬约束：违反则严重惩罚
        for constraint in self.hard_constraints:
            violation = constraint(x)
            if violation > 0:
                bias += 100.0 * violation  # 大惩罚

        # 软约束：违反则适度惩罚
        for constraint in self.soft_constraints:
            violation = constraint(x)
            if violation > 0:
                bias += 10.0 * violation

        # 偏好约束：满足则奖励
        for constraint in self.preferred_constraints:
            satisfaction = constraint(x)
            bias -= 1.0 * satisfaction  # 负值表示奖励

        return self.weight * bias


class PreferenceBias(DomainBias):
    """偏好偏置：体现业务偏好"""

    def __init__(self, weight: float = 0.1):
        super().__init__("preference", weight)
        self.preferences = {}

    def set_preference(self, metric: str, direction: str, weight: float = 1.0):
        """设置偏好
        direction: 'minimize' 或 'maximize'
        """
        self.preferences[metric] = {'direction': direction, 'weight': weight}

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        bias = 0.0

        for metric, pref in self.preferences.items():
            if metric in context.metrics:
                value = context.metrics[metric]
                pref_weight = pref['weight']

                if pref['direction'] == 'minimize':
                    bias += self.weight * pref_weight * value
                else:  # maximize
                    bias -= self.weight * pref_weight * value  # 负值表示奖励

        return bias


class ObjectiveBias(DomainBias):
    """目标偏置：引导向理想目标方向"""

    def __init__(self, weight: float = 0.1):
        super().__init__("objective", weight)
        self.target_values = {}
        self.directions = {}

    def set_target(self, objective: str, target: float, direction: str = 'minimize'):
        """设置目标值
        direction: 'minimize' 或 'maximize'
        """
        self.target_values[objective] = target
        self.directions[objective] = direction

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        bias = 0.0

        for obj, target in self.target_values.items():
            if obj in context.metrics:
                current = context.metrics[obj]
                direction = self.directions[obj]

                # 计算与目标的距离
                if direction == 'minimize':
                    # 越小越好，但也不能太小
                    if current < target:
                        bias += self.weight * (target - current) * 10  # 惩罚过小
                    else:
                        bias += self.weight * (current - target)  # 奖励接近
                else:  # maximize
                    # 越大越好，但不能太大
                    if current > target:
                        bias -= self.weight * (current - target) * 10  # 奖励超额
                    else:
                        bias -= self.weight * (target - current)  # 惩罚不足

        return bias


# ==================== 偏置管理器 ====================

class AlgorithmicBiasManager:
    """算法偏置管理器"""

    def __init__(self):
        self.biases = {}

    def add_bias(self, bias: AlgorithmicBias):
        """添加算法偏置"""
        self.biases[bias.name] = bias

    def remove_bias(self, name: str):
        """移除算法偏置"""
        if name in self.biases:
            del self.biases[name]

    def get_bias(self, name: str) -> Optional[AlgorithmicBias]:
        """获取偏置"""
        return self.biases.get(name)

    def compute_algorithmic_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总的算法偏置"""
        total_bias = 0.0
        for bias in self.biases.values():
            if bias.enabled:
                total_bias += bias.compute(x, context)
        return total_bias

    def enable_all(self):
        """启用所有偏置"""
        for bias in self.biases.values():
            bias.enable()

    def disable_all(self):
        """禁用所有偏置"""
        for bias in self.biases.values():
            bias.disable()


class DomainBiasManager:
    """业务偏置管理器"""

    def __init__(self):
        self.biases = {}

    def add_bias(self, bias: DomainBias):
        """添加业务偏置"""
        self.biases[bias.name] = bias

    def remove_bias(self, name: str):
        """移除业务偏置"""
        if name in self.biases:
            del self.biases[name]

    def get_bias(self, name: str) -> Optional[DomainBias]:
        """获取偏置"""
        return self.biases.get(name)

    def compute_domain_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总的业务偏置"""
        total_bias = 0.0
        for bias in self.biases.values():
            if bias.enabled:
                total_bias += bias.compute(x, context)
        return total_bias


class UniversalBiasManager:
    """通用偏置管理器：协调算法偏置和业务偏置"""

    def __init__(self, algorithm_config: Dict = None, domain_config: Dict = None):
        self.algorithmic_manager = AlgorithmicBiasManager()
        self.domain_manager = DomainBiasManager()

        # 偏置权重配置
        self.bias_weights = {
            'algorithmic': 0.3,  # 算法偏置权重
            'domain': 0.7       # 业务偏置权重（业务更重要）
        }

        # 初始化算法偏置
        if algorithm_config:
            self._initialize_algorithmic_biases(algorithm_config)
        else:
            # 默认算法偏置
            self._initialize_default_algorithmic_biases()

        # 初始化业务偏置
        if domain_config:
            self._initialize_domain_biases(domain_config)

    def _initialize_default_algorithmic_biases(self):
        """初始化默认算法偏置"""
        self.algorithmic_manager.add_bias(DiversityBias(weight=0.1))
        self.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

    def _initialize_algorithmic_biases(self, config):
        """根据配置初始化算法偏置"""
        bias_configs = config.get('biases', [])

        for bias_config in bias_configs:
            bias_type = bias_config['type']
            params = bias_config.get('parameters', {})

            if bias_type == 'diversity':
                self.algorithmic_manager.add_bias(DiversityBias(**params))
            elif bias_type == 'convergence':
                self.algorithmic_manager.add_bias(ConvergenceBias(**params))
            elif bias_type == 'exploration':
                self.algorithmic_manager.add_bias(ExplorationBias(**params))
            elif bias_type == 'precision':
                bias = PrecisionBias(**params)
                # 如果有已知的好的解，添加进去
                if 'known_solutions' in params:
                    for sol in params['known_solutions']:
                        bias.add_good_solution(np.array(sol))
                self.algorithmic_manager.add_bias(bias)

    def _initialize_domain_biases(self, config):
        """根据配置初始化业务偏置"""
        bias_configs = config.get('biases', [])

        for bias_config in bias_configs:
            bias_type = bias_config['type']
            params = bias_config.get('parameters', {})

            if bias_type == 'constraint':
                bias = ConstraintBias(**params)
                # 添加约束函数
                if 'hard_constraints' in params:
                    for constraint in params['hard_constraints']:
                        bias.add_hard_constraint(constraint)
                if 'soft_constraints' in params:
                    for constraint in params['soft_constraints']:
                        bias.add_soft_constraint(constraint)
                if 'preferred_constraints' in params:
                    for constraint in params['preferred_constraints']:
                        bias.add_preferred_constraint(constraint)
                self.domain_manager.add_bias(bias)

            elif bias_type == 'preference':
                bias = PreferenceBias(**params)
                if 'preferences' in params:
                    for pref in params['preferences']:
                        bias.set_preference(**pref)
                self.domain_manager.add_bias(bias)

            elif bias_type == 'objective':
                bias = ObjectiveBias(**params)
                if 'targets' in params:
                    for target in params['targets']:
                        bias.set_target(**target)
                self.domain_manager.add_bias(bias)

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总偏置"""

        # 算法层面偏置
        alg_bias = self.algorithmic_manager.compute_algorithmic_bias(x, context)

        # 业务层面偏置
        domain_bias = self.domain_manager.compute_domain_bias(x, context)

        # 加权组合
        total_bias = (self.bias_weights['algorithmic'] * alg_bias +
                     self.bias_weights['domain'] * domain_bias)

        return total_bias

    def adjust_weights(self, optimization_state: Dict[str, Any]):
        """根据优化状态动态调整权重"""

        if optimization_state.get('is_stuck', False):
            # 陷入局部最优，增加算法偏置
            self.bias_weights['algorithmic'] = min(0.7, self.bias_weights['algorithmic'] + 0.1)
            self.bias_weights['domain'] = 1.0 - self.bias_weights['algorithmic']

        elif optimization_state.get('is_violating_constraints', False):
            # 违反约束，增加业务偏置
            self.bias_weights['domain'] = min(0.9, self.bias_weights['domain'] + 0.1)
            self.bias_weights['algorithmic'] = 1.0 - self.bias_weights['domain']

    def set_bias_weights(self, algorithmic_weight: float, domain_weight: float):
        """设置偏置权重"""
        total = algorithmic_weight + domain_weight
        if total > 0:
            self.bias_weights['algorithmic'] = algorithmic_weight / total
            self.bias_weights['domain'] = domain_weight / total

    def get_algorithmic_bias(self, name: str) -> Optional[AlgorithmicBias]:
        """获取算法偏置"""
        return self.algorithmic_manager.get_bias(name)

    def get_domain_bias(self, name: str) -> Optional[DomainBias]:
        """获取业务偏置"""
        return self.domain_manager.get_bias(name)

    def save_config(self, filepath: str):
        """保存配置到文件"""
        config = {
            'bias_weights': self.bias_weights,
            'algorithmic_biases': {},
            'domain_biases': {}
        }

        # 保存算法偏置配置
        for name, bias in self.algorithmic_manager.biases.items():
            config['algorithmic_biases'][name] = {
                'type': bias.__class__.__name__,
                'weight': bias.weight,
                'enabled': bias.enabled
            }

        # 保存业务偏置配置
        for name, bias in self.domain_manager.biases.items():
            config['domain_biases'][name] = {
                'type': bias.__class__.__name__,
                'weight': bias.weight,
                'enabled': bias.enabled
            }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

    def load_config(self, filepath: str):
        """从文件加载配置"""
        with open(filepath, 'r') as f:
            config = json.load(f)

        self.bias_weights = config.get('bias_weights', self.bias_weights)

        # 这里可以进一步加载具体的偏置配置
        # 但需要根据实际的偏置类型来创建实例


# ==================== 偏置模板系统 ====================

BASIC_ENGINEERING_TEMPLATE = {
    'algorithmic': {
        'type': 'diversity_convergence_mix',
        'parameters': {
            'diversity_weight': 0.15,
            'convergence_weight': 0.1
        }
    },
    'domain': {
        'type': 'engineering_design',
        'parameters': {
            'hard_constraints': ['stress_limits', 'material_properties'],
            'soft_constraints': ['weight_limit', 'cost_limit'],
            'preferences': [
                {'metric': 'reliability', 'direction': 'maximize', 'weight': 2.0},
                {'metric': 'manufacturability', 'direction': 'maximize', 'weight': 1.0}
            ]
        }
    }
}

FINANCIAL_OPTIMIZATION_TEMPLATE = {
    'algorithmic': {
        'type': 'fast_convergence',
        'parameters': {
            'early_gen': 5,
            'late_gen': 30
        }
    },
    'domain': {
        'type': 'financial_optimization',
        'parameters': {
            'hard_constraints': ['budget_limits', 'risk_limits'],
            'preferences': [
                {'metric': 'return', 'direction': 'maximize', 'weight': 3.0},
                {'metric': 'risk', 'direction': 'minimize', 'weight': 2.0}
            ]
        }
    }
}

MACHINE_LEARNING_TEMPLATE = {
    'algorithmic': {
        'type': 'precision_search',
        'parameters': {
            'precision_radius': 0.05
        }
    },
    'domain': {
        'type': 'machine_learning',
        'parameters': {
            'hard_constraints': ['training_time_limit', 'memory_limit'],
            'preferences': [
                {'metric': 'accuracy', 'direction': 'maximize', 'weight': 4.0},
                {'metric': 'model_complexity', 'direction': 'minimize', 'weight': 1.0}
            ]
        }
    }
}


def create_bias_manager_from_template(template_name: str, customizations: Dict = None) -> UniversalBiasManager:
    """从模板创建偏置管理器"""

    templates = {
        'basic_engineering': BASIC_ENGINEERING_TEMPLATE,
        'financial_optimization': FINANCIAL_OPTIMIZATION_TEMPLATE,
        'machine_learning': MACHINE_LEARNING_TEMPLATE
    }

    if template_name not in templates:
        raise ValueError(f"Unknown template: {template_name}")

    config = templates[template_name].copy()

    # 应用自定义配置
    if customizations:
        if 'algorithmic' in customizations:
            config['algorithmic'].update(customizations['algorithmic'])
        if 'domain' in customizations:
            config['domain'].update(customizations['domain'])

    return UniversalBiasManager(
        algorithm_config=config.get('algorithmic'),
        domain_config=config.get('domain')
    )


# ==================== 便捷创建函数 ====================

def create_engineering_bias(constraints: List = None, preferences: List = None) -> UniversalBiasManager:
    """创建工程设计偏置管理器"""
    config = {
        'biases': [
            {
                'type': 'constraint',
                'parameters': {
                    'hard_constraints': constraints or [],
                    'soft_constraints': []
                }
            },
            {
                'type': 'preference',
                'parameters': {
                    'preferences': preferences or []
                }
            }
        ]
    }

    return UniversalBiasManager(domain_config=config)


def create_ml_bias(time_limit: float = 3600, memory_limit: float = 8.0) -> UniversalBiasManager:
    """创建机器学习偏置管理器"""

    def time_constraint(x):
        # 这里应该是实际的时间评估函数
        return 0.0  # 简化实现

    def memory_constraint(x):
        # 这里应该是实际的内存评估函数
        return 0.0  # 简化实现

    config = {
        'biases': [
            {
                'type': 'constraint',
                'parameters': {
                    'hard_constraints': [time_constraint, memory_constraint]
                }
            },
            {
                'type': 'preference',
                'parameters': {
                    'preferences': [
                        {'metric': 'accuracy', 'direction': 'maximize', 'weight': 4.0},
                        {'metric': 'complexity', 'direction': 'minimize', 'weight': 1.0}
                    ]
                }
            }
        ]
    }

    return UniversalBiasManager(domain_config=config)