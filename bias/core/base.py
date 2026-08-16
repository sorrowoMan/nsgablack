"""
偏置系统基础类和接口定义

Inherits the unified BiasBase from blackbase and adds nsgablack-specific
features (compute-based bias, OptimizationContext, tracking, statistics,
AlgorithmicBias/DomainBias subtypes).

偏置系统是NSGABlack优化库的核心创新，实现算法策略与领域知识的分离。
"""

import numpy as np
import time
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from blackbase.abc import BiasBase as _BiasBase

logger = logging.getLogger(__name__)


@runtime_checkable
class BiasInterface(Protocol):
    """统一偏置接口协议，用于约束偏置实现的公共方法。"""

    def compute(self, x: np.ndarray, context: "OptimizationContext") -> float:
        ...

    def get_name(self) -> str:
        ...

    def get_weight(self) -> float:
        ...

    def set_weight(self, weight: float) -> None:
        ...

    def enable(self) -> None:
        ...

    def disable(self) -> None:
        ...


class OptimizationContext:
    """
    优化上下文信息类

    封装当前优化状态的所有相关信息，包括：
    - 当前代数、个体、种群
    - 性能指标、历史数据
    - 优化状态标志（停滞、收敛、约束违反等）

    该类为偏置计算提供必要的上下文环境。
    """

    def __init__(
        self,
        generation: int,
        individual: np.ndarray,
        population: Optional[List[np.ndarray]] = None,
        metrics: Optional[Dict[str, float]] = None,
        history: Optional[List] = None,
        problem_data: Optional[Dict[str, Any]] = None
    ):
        self.generation = generation
        self.individual = individual
        self.population = population if population is not None else []
        self.metrics = metrics or {}
        self.history = history or []
        self.problem_data = problem_data or {}

        # 派生的上下文状态标志
        self.is_stuck = False
        self.is_converging = False
        self.is_violating_constraints = False

    def set_stuck_status(self, is_stuck: bool):
        self.is_stuck = is_stuck

    def set_convergence_status(self, is_converging: bool):
        self.is_converging = is_converging

    def set_constraint_violation(self, is_violating: bool):
        self.is_violating_constraints = is_violating


class BiasBase(_BiasBase, BiasInterface):
    """
    nsgablack BiasBase: inherits blackbase BiasBase and adds compute-based
    bias with tracking, statistics, and OptimizationContext support.

    In nsgablack, bias expresses preference in multi-objective optimization
    by computing a scalar bias value that adjusts selection pressure.
    """

    # Class-level context contract defaults
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = None
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, name: str, weight: float = 1.0, description: str = ""):
        self.name = name
        self.weight = weight
        self.description = description
        self.enabled = True
        self.usage_count = 0
        self.total_bias_value = 0.0

        # 参数变化回调
        self._param_change_callbacks = []

        # 详细统计信息
        self._per_generation_values = []
        self._recent_values = []
        self._max_history = 100
        self._current_generation_values = []

        # Keep instance-level copies for backward compatibility
        self.context_requires = tuple(getattr(self, "context_requires", ()) or ())
        self.context_provides = tuple(getattr(self, "context_provides", ()) or ())
        self.context_mutates = tuple(getattr(self, "context_mutates", ()) or ())
        self.context_cache = tuple(getattr(self, "context_cache", ()) or ())
        self.context_notes = getattr(self, "context_notes", None)
        self.requires_metrics = tuple(getattr(self, "requires_metrics", ()) or ())
        self.metrics_fallback = str(getattr(self, "metrics_fallback", "none") or "none").strip().lower()
        self.missing_metrics_policy = str(getattr(self, "missing_metrics_policy", "warn") or "warn").strip().lower()
        self._missing_metrics_reported = set()

    # --- nsgablack-specific: compute-based bias ---

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算给定个体和上下文的偏置值。

        默认实现返回 0.0。子类应重写此方法以定义具体的偏置逻辑。
        """
        return 0.0

    def compute_with_tracking(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算偏置值并跟踪使用统计信息。"""
        if not self.enabled:
            return 0.0

        self._enforce_required_metrics(context)

        bias_value = self.compute(x, context)
        weighted_value = bias_value * self.weight

        self.usage_count += 1
        self.total_bias_value += abs(bias_value)

        value_record = {
            'generation': context.generation,
            'raw_value': float(bias_value),
            'weighted_value': float(weighted_value),
            'timestamp': time.time()
        }
        self._recent_values.append(value_record)
        self._current_generation_values.append(weighted_value)

        if len(self._recent_values) > self._max_history:
            self._recent_values.pop(0)

        return weighted_value

    # --- Override: adjust delegates to compute ---

    def adjust(self, feedback, context=None):
        """Apply preference adjustment. In nsgablack, this is compute-based."""
        return feedback

    # --- Override: extended context contract ---

    def get_context_contract(self) -> Dict[str, Any]:
        requires = list(getattr(self, "context_requires", ()) or ())
        metric_keys = getattr(self, "requires_metrics", ()) or ()
        for key in metric_keys:
            text = str(key).strip()
            if not text:
                continue
            if text.startswith("metrics."):
                requires.append(text)
            else:
                requires.append(f"metrics.{text}")

        notes_parts: List[str] = []
        base_notes = getattr(self, "context_notes", None)
        if base_notes:
            notes_parts.append(str(base_notes))
        rec_plugins = getattr(self, "recommended_plugins", ()) or ()
        if rec_plugins:
            notes_parts.append("recommended_plugins=" + ", ".join(str(x) for x in rec_plugins))
        if metric_keys:
            metric_list = [str(x).strip() for x in metric_keys if str(x).strip()]
            if metric_list:
                notes_parts.append("requires_metrics=" + ", ".join(metric_list))
        policy = str(getattr(self, "missing_metrics_policy", "warn") or "warn").strip().lower()
        if policy:
            notes_parts.append(f"missing_metrics_policy={policy}")
        fallback = str(getattr(self, "metrics_fallback", "none") or "none").strip().lower()
        if fallback:
            notes_parts.append(f"metrics_fallback={fallback}")

        return {
            "requires": requires,
            "provides": getattr(self, "context_provides", ()),
            "mutates": getattr(self, "context_mutates", ()),
            "cache": getattr(self, "context_cache", ()),
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

    def _enforce_required_metrics(self, context: OptimizationContext) -> None:
        missing = self._missing_required_metrics(context)
        if not missing:
            return

        policy = str(getattr(self, "missing_metrics_policy", "warn") or "warn").strip().lower()
        generation = int(getattr(context, "generation", -1) or -1)
        marker = (generation, tuple(missing))
        message = (
            f"Bias '{self.name}' missing required metrics: {', '.join(missing)} "
            f"(policy={policy})."
        )

        if policy == "error":
            raise KeyError(message)
        if policy in {"ignore", "none", "off"}:
            return
        if marker in self._missing_metrics_reported:
            return
        self._missing_metrics_reported.add(marker)
        logger.warning(message)

    def _missing_required_metrics(self, context: OptimizationContext) -> List[str]:
        metric_keys = tuple(getattr(self, "requires_metrics", ()) or ())
        if not metric_keys:
            return []

        metrics_obj = getattr(context, "metrics", {})
        metrics = metrics_obj if isinstance(metrics_obj, dict) else {}
        available = {str(k).strip() for k in metrics.keys() if str(k).strip()}

        missing: List[str] = []
        for key in metric_keys:
            text = str(key).strip()
            if not text:
                continue
            short_key = text.split(".", 1)[1] if text.startswith("metrics.") else text
            if short_key in available or f"metrics.{short_key}" in available:
                continue
            missing.append(short_key)
        return sorted(set(missing))

    # --- Callbacks ---

    def register_param_change_callback(self, callback: Callable[["BiasBase"], None]):
        if callback not in self._param_change_callbacks:
            self._param_change_callbacks.append(callback)

    def _notify_param_change(self):
        for cb in list(self._param_change_callbacks):
            try:
                cb(self)
            except Exception:
                pass

    # --- Override: weight/enable with callbacks ---

    def set_weight(self, weight: float):
        self.weight = max(0.0, weight)
        self._notify_param_change()

    def enable(self):
        self.enabled = True
        self._notify_param_change()

    def disable(self):
        self.enabled = False
        self._notify_param_change()

    # --- Statistics ---

    def get_average_bias(self) -> float:
        return self.total_bias_value / max(1, self.usage_count)

    def reset_statistics(self):
        self.usage_count = 0
        self.total_bias_value = 0.0
        self._per_generation_values = []
        self._recent_values = []
        self._current_generation_values = []

    def finalize_generation(self, generation: int):
        if not self._current_generation_values:
            return

        values = self._current_generation_values
        gen_stats = {
            'generation': generation,
            'avg_bias': sum(values) / len(values) if values else 0.0,
            'call_count': len(values),
            'min_bias': min(values) if values else 0.0,
            'max_bias': max(values) if values else 0.0,
            'std_bias': np.std(values) if len(values) > 1 else 0.0
        }

        self._per_generation_values.append(gen_stats)
        self._current_generation_values = []

    def get_statistics(self) -> Dict[str, Any]:
        if self.usage_count == 0:
            return {
                'name': self.name,
                'enabled': self.enabled,
                'weight': self.weight,
                'usage_count': 0,
                'message': 'Never used'
            }

        return {
            'name': self.name,
            'enabled': self.enabled,
            'weight': self.weight,
            'usage_count': self.usage_count,
            'total_contribution': self.total_bias_value,
            'average_contribution': self.get_average_bias(),
            'per_generation_stats': self._per_generation_values,
            'recent_values': self._recent_values[-10:],
            'bias_type': getattr(self, 'bias_type', 'unknown')
        }

    def __str__(self) -> str:
        return f"{self.name}(weight={self.weight}, enabled={self.enabled})"


class AlgorithmicBias(BiasBase):
    """
    算法偏置基类

    算法偏置控制搜索策略和优化行为，典型特征：
    - 可自适应调整权重
    - 基于优化状态动态变化
    - 引导搜索方向和探索-开发平衡
    """
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        adaptive: bool = True,
        description: str = ""
    ):
        super().__init__(name, weight, description)
        self.bias_type = 'algorithmic'
        self.adaptive = adaptive
        self.initial_weight = weight

    def is_adaptive(self) -> bool:
        return self.adaptive

    def reset_to_initial_weight(self):
        self.weight = self.initial_weight


class DomainBias(BiasBase):
    """
    领域偏置基类

    领域偏置融入业务知识和约束条件，典型特征：
    - 代表强制性业务规则
    - 权重通常固定不变
    - 处理约束、偏好、领域知识
    """
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        mandatory: bool = False,
        description: str = ""
    ):
        super().__init__(name, weight, description)
        self.bias_type = 'domain'
        self.mandatory = mandatory

    def is_mandatory(self) -> bool:
        return self.mandatory


# Protocol for bias managers
class BiasManager(Protocol):
    """偏置管理器协议定义"""

    def add_bias(self, bias: BiasBase): ...
    def remove_bias(self, name: str) -> bool: ...
    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float: ...
    def get_bias(self, name: str) -> Optional[BiasBase]: ...


# Factory function
def create_bias(
    bias_type: str,
    name: str,
    weight: float = 1.0,
    **kwargs
) -> BiasBase:
    """创建偏置实例的工厂函数"""
    if bias_type.lower() == 'algorithmic':
        return AlgorithmicBias(name, weight, **kwargs)
    elif bias_type.lower() == 'domain':
        return DomainBias(name, weight, **kwargs)
    else:
        raise ValueError(f"不支持的偏置类型: {bias_type}。支持的类型: 'algorithmic', 'domain'")
