"""
通用偏置管理器实现

该模块提供偏置系统的核心管理功能，包括：
- 算法偏置和领域偏置的分离管理
- 偏置组合和计算逻辑
- 历史记录和统计分析
- 配置保存和加载

管理器是偏置系统的核心，协调各种偏置的协同工作。
"""

import numpy as np
from typing import Dict, List, Any, Optional, Union
import json
from pathlib import Path

from .base import (
    BiasBase, AlgorithmicBias, DomainBias, OptimizationContext,
    BiasManager
)


class BiasManagerMixin:
    """
    偏置管理器混入类 - 提供通用管理功能

    为不同类型的偏置管理器提供基础功能：
    - 偏置添加和移除
    - 偏置列表和统计
    - 启用/禁用控制
    """

    def __init__(self):
        self.biases: Dict[str, BiasBase] = {}            # 偏置字典

    def add_bias(self, bias: BiasBase) -> bool:
        """
        添加偏置到管理器

        Args:
            bias: 要添加的偏置对象

        Returns:
            True if added successfully, False if name already exists

        Note:
            如果偏置名称已存在，将覆盖原有偏置
        """
        if bias.name in self.biases:
            print(f"警告: 偏置 '{bias.name}' 已存在，将被覆盖")

        self.biases[bias.name] = bias
        return True

    def remove_bias(self, name: str) -> bool:
        """
        根据名称移除偏置

        Args:
            name: 偏置名称

        Returns:
            True if removed successfully, False if not found
        """
        if name in self.biases:
            del self.biases[name]
            return True
        return False

    def get_bias(self, name: str) -> Optional[BiasBase]:
        """
        根据名称获取偏置对象

        Args:
            name: 偏置名称

        Returns:
            偏置对象，如果不存在则返回None
        """
        return self.biases.get(name)

    def list_biases(self) -> List[str]:
        """
        列出所有偏置名称

        Returns:
            偏置名称列表
        """
        return list(self.biases.keys())

    def enable_all(self):
        """启用所有偏置"""
        for bias in self.biases.values():
            bias.enable()

    def disable_all(self):
        """禁用所有偏置"""
        for bias in self.biases.values():
            bias.disable()

    def get_enabled_biases(self) -> List[BiasBase]:
        """
        获取所有启用的偏置

        Returns:
            启用的偏置对象列表
        """
        return [bias for bias in self.biases.values() if bias.enabled]

    def get_bias_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有偏置的使用统计信息

        Returns:
            每个偏置的统计信息字典
        """
        stats = {}
        for name, bias in self.biases.items():
            stats[name] = {
                'type': bias.bias_type,
                'weight': bias.weight,
                'enabled': bias.enabled,
                'usage_count': bias.usage_count,
                'average_bias': bias.get_average_bias(),
                'total_bias_value': bias.total_bias_value
            }
        return stats


class AlgorithmicBiasManager(BiasManagerMixin):
    """
    算法偏置管理器

    专门管理算法层面的偏置，特点：
    - 控制搜索策略和优化行为
    - 支持自适应权重调整
    - 动态响应优化状态变化
    - 历史性能跟踪

    算法偏置影响"如何搜索"，而不是"搜索什么"。
    """

    def __init__(self):
        super().__init__()
        self.adaptive_weights = True                        # 是否启用自适应权重
        self.performance_history = []                    # 性能历史记录
        self.stuck_threshold = 10                          # 停滞检测阈值

    def add_algorithmic_bias(self, bias: AlgorithmicBias) -> bool:
        """
        添加算法偏置

        Args:
            bias: 算法偏置对象

        Returns:
            True if added successfully

        Raises:
            TypeError: 如果不是AlgorithmicBias实例
        """
        if not isinstance(bias, AlgorithmicBias):
            raise TypeError("只能添加AlgorithmicBias实例到AlgorithmicBiasManager")
        return self.add_bias(bias)

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算算法偏置总值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            总算法偏置值
        """
        total_bias = 0.0
        for bias in self.get_enabled_biases():
            if isinstance(bias, AlgorithmicBias):
                bias_value = bias.compute_with_tracking(x, context)
                total_bias += bias_value
        return total_bias

    def adapt_weights(self, context: OptimizationContext, performance_metric: float):
        """
        自适应调整偏置权重

        根据优化状态和性能指标动态调整偏置权重：
        - 检测停滞状态时增强探索性偏置
        - 检测收敛状态时增强收敛性偏置
        - 记录调整历史用于分析

        Args:
            context: 优化上下文
            performance_metric: 性能指标
        """
        if not self.adaptive_weights:
            return

        # 检测优化状态并调整权重
        if context.is_stuck:
            # 陷入停滞：增强探索性偏置
            self.adjust_exploration_weights(1.2)
        elif context.is_converging:
            # 正在收敛：增强收敛性偏置
            self.adjust_convergence_weights(1.1)

        # 记录性能历史
        self.performance_history.append({
            'generation': context.generation,
            'performance': performance_metric,
            'bias_weights': {name: bias.weight for name, bias in self.biases.items()}
        })

    def adjust_exploration_weights(self, factor: float):
        """
        调整探索性偏置权重

        Args:
            factor: 调整因子（>1增强，<1减弱）
        """
        exploration_keywords = ['diversity', 'exploration', 'simulated_annealing']
        for bias in self.biases.values():
            if any(keyword in bias.name.lower() for keyword in exploration_keywords):
                bias.weight *= factor

    def adjust_convergence_weights(self, factor: float):
        """
        调整收敛性偏置权重

        Args:
            factor: 调整因子（>1增强，<1减弱）
        """
        convergence_keywords = ['convergence', 'local_search', 'precision']
        for bias in self.biases.values():
            if any(keyword in bias.name.lower() for keyword in convergence_keywords):
                bias.weight *= factor

    def reset_adaptive_weights(self):
        """重置所有自适应偏置到初始权重"""
        for bias in self.biases.values():
            if isinstance(bias, AlgorithmicBias) and bias.adaptive:
                bias.reset_to_initial_weight()


class DomainBiasManager(BiasManagerMixin):
    """
    领域偏置管理器

    专门管理领域层面的偏置，特点：
    - 融入业务知识和约束条件
    - 权重通常固定不变
    - 代表强制性的业务规则
    - 与算法偏置协同工作

    领域偏置影响"搜索什么"，确保结果满足业务要求。
    """

    def __init__(self):
        super().__init__()
        self.constraint_violation_history = []            # 约束违反历史
        self.violation_trend = []                          # 违反趋势

    def add_domain_bias(self, bias: DomainBias) -> bool:
        """
        添加领域偏置

        Args:
            bias: 领域偏置对象

        Returns:
            True if added successfully

        Raises:
            TypeError: 如果不是DomainBias实例
        """
        if not isinstance(bias, DomainBias):
            raise TypeError("只能添加DomainBias实例到DomainBiasManager")
        return self.add_bias(bias)

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算领域偏置总值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            总领域偏置值
        """
        total_bias = 0.0
        for bias in self.get_enabled_biases():
            if isinstance(bias, DomainBias):
                bias_value = bias.compute_with_tracking(x, context)
                total_bias += bias_value

        # 跟踪约束违反情况
        if total_bias > 0:
            context.set_constraint_violation(True)
            self.constraint_violation_history.append({
                'generation': context.generation,
                'violation_amount': total_bias
            })

        return total_bias

    def get_mandatory_biases(self) -> List[DomainBias]:
        """
        获取所有强制性领域偏置

        Returns:
            强制性偏置列表
        """
        return [bias for bias in self.biases.values()
                if isinstance(bias, DomainBias) and bias.is_mandatory()]

    def ensure_mandatory_enabled(self):
        """确保所有强制性偏置都启用"""
        for bias in self.get_mandatory_biases():
            bias.enable()

    def compute_constraint_violation_rate(self) -> float:
        """
        计算约束违反率

        Returns:
            约束违反率（0-1之间）
        """
        if not self.constraint_violation_history:
            return 0.0

        # 简化实现：违反次数 / 总评估次数
        total_violations = len(self.constraint_violation_history)
        # 这里需要一个总评估次数的计数器
        total_evaluations = total_violations * 10  # 简化假设
        return total_violations / max(1, total_evaluations)


class UniversalBiasManager:
    """
    通用偏置管理器 - 偏置系统的核心

    统一管理算法偏置和领域偏置：
    - 分离管理算法和领域关注点
    - 提供统一的偏置计算接口
    - 支持偏置组合和协同工作
    - 完整的配置和持久化功能

    这是偏置系统的主要入口点，为用户提供完整的偏置管理能力。
    """

    def __init__(self):
        """
        初始化通用偏置管理器
        """
        self.algorithmic_manager = AlgorithmicBiasManager()  # 算法偏置管理器
        self.domain_manager = DomainBiasManager()           # 领域偏置管理器
        self.total_bias_calls = 0                          # 总调用次数
        self.bias_history = []                              # 偏置历史记录

    def add_algorithmic_bias(self, bias: AlgorithmicBias):
        """
        添加算法偏置

        Args:
            bias: 算法偏置对象
        """
        return self.algorithmic_manager.add_algorithmic_bias(bias)

    def add_domain_bias(self, bias: DomainBias):
        """
        添加领域偏置

        Args:
            bias: 领域偏置对象
        """
        return self.domain_manager.add_domain_bias(bias)

    def compute_total_bias(
        self,
        x: np.ndarray,
        context: OptimizationContext,
        performance_metric: Optional[float] = None
    ) -> Dict[str, float]:
        """
        计算总偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文
            performance_metric: 性能指标（用于自适应调整）

        Returns:
            包含各种偏置贡献和总数的字典：
            {
                'algorithmic_bias': 算法偏置值,
                'domain_bias': 领域偏置值,
                'total_bias': 总偏置值
            }
        """
        self.total_bias_calls += 1

        # 计算算法偏置
        algorithmic_bias = self.algorithmic_manager.compute_total_bias(x, context)

        # 计算领域偏置
        domain_bias = self.domain_manager.compute_total_bias(x, context)

        # 计算总偏置
        total_bias = algorithmic_bias + domain_bias

        # 记录偏置历史
        self.bias_history.append({
            'generation': context.generation,
            'algorithmic_bias': algorithmic_bias,
            'domain_bias': domain_bias,
            'total_bias': total_bias
        })

        # 自适应调整算法偏置权重
        if performance_metric is not None:
            self.algorithmic_manager.adapt_weights(context, performance_metric)

        return {
            'algorithmic_bias': algorithmic_bias,
            'domain_bias': domain_bias,
            'total_bias': total_bias
        }

    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """
        获取全面的偏置统计信息

        Returns:
            包含各种统计指标的详细字典
        """
        return {
            'total_bias_calls': self.total_bias_calls,
            'algorithmic_biases': self.algorithmic_manager.get_bias_statistics(),
            'domain_biases': self.domain_manager.get_bias_statistics(),
            'constraint_violation_rate': self.domain_manager.compute_constraint_violation_rate(),
            'bias_history_summary': {
                'total_entries': len(self.bias_history),
                'avg_total_bias': np.mean([h['total_bias'] for h in self.bias_history]) if self.bias_history else 0,
                'max_total_bias': max([h['total_bias'] for h in self.bias_history]) if self.bias_history else 0,
                'min_total_bias': min([h['total_bias'] for h in self.bias_history]) if self.bias_history else 0
            }
        }

    def save_configuration(self, filepath: Union[str, Path]):
        """
        保存当前偏置配置到文件

        Args:
            filepath: 配置文件路径
        """
        config = {
            'algorithmic_biases': {
                name: {
                    'weight': bias.weight,
                    'enabled': bias.enabled,
                    'adaptive': bias.adaptive if isinstance(bias, AlgorithmicBias) else False
                }
                for name, bias in self.algorithmic_manager.biases.items()
            },
            'domain_biases': {
                name: {
                    'weight': bias.weight,
                    'enabled': bias.enabled,
                    'mandatory': bias.is_mandatory() if isinstance(bias, DomainBias) else False
                }
                for name, bias in self.domain_manager.biases.items()
            },
            'metadata': {
                'timestamp': self._get_timestamp(),
                'version': '2.0.0',
                'total_calls': self.total_bias_calls
            }
        }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def load_configuration(self, filepath: Union[str, Path]):
        """
        从文件加载偏置配置

        Args:
            filepath: 配置文件路径
        """
        with open(filepath, 'r') as f:
            config = json.load(f)

        # 应用算法偏置配置
        for name, bias_config in config.get('algorithmic_biases', {}).items():
            bias = self.algorithmic_manager.get_bias(name)
            if bias:
                bias.set_weight(bias_config['weight'])
                if bias_config['enabled']:
                    bias.enable()
                else:
                    bias.disable()

        # 应用领域偏置配置
        for name, bias_config in config.get('domain_biases', {}).items():
            bias = self.domain_manager.get_bias(name)
            if bias:
                bias.set_weight(bias_config['weight'])
                if bias_config['enabled']:
                    bias.enable()
                else:
                    bias.disable()

    def reset_all_statistics(self):
        """重置所有偏置的统计信息"""
        for bias in self.algorithmic_manager.biases.values():
            bias.reset_statistics()

        for bias in self.domain_manager.biases.values():
            bias.reset_statistics()

        self.total_bias_calls = 0
        self.bias_history = []

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def __str__(self) -> str:
        """字符串表示"""
        algo_count = len(self.algorithmic_manager.biases)
        domain_count = len(self.domain_manager.biases)
        return f"UniversalBiasManager(algorithmic={algo_count}, domain={domain_count})"