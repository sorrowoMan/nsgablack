"""
BiasModule - 兼容适配器

提供与旧版本 solver.py 接口兼容的 BiasModule 实现。
该适配器封装了新的 UniversalBiasManager，使其能够与现有代码无缝集成。

设计原则：
1. 保持向后兼容：现有代码无需修改即可使用新偏置系统
2. 逐步迁移：新代码可以直接使用 UniversalBiasManager
3. 统一接口：提供一致的偏置管理体验
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING, Set
import copy
import logging
import warnings
import numpy as np
from collections import OrderedDict
import inspect

if TYPE_CHECKING:
    from .core.manager import UniversalBiasManager
    from .core.base import OptimizationContext, BiasBase, AlgorithmicBias, DomainBias, BiasInterface

try:
    from .core.manager import UniversalBiasManager as UniversalBiasManagerImpl
    from .core.base import (
        OptimizationContext as OptimizationContextImpl,
        BiasBase as BiasBaseImpl,
        AlgorithmicBias as AlgorithmicBiasImpl,
        DomainBias as DomainBiasImpl,
        BiasInterface as BiasInterfaceImpl,
    )
    NEW_SYSTEM_AVAILABLE = True
except ImportError:
    UniversalBiasManagerImpl = None
    OptimizationContextImpl = None
    BiasBaseImpl = None
    AlgorithmicBiasImpl = None
    DomainBiasImpl = None
    BiasInterfaceImpl = None
    NEW_SYSTEM_AVAILABLE = False

# 模块级日志器
logger = logging.getLogger(__name__)


class BiasModule:
    """
    偏置模块 - 兼容适配器

    该类提供了与旧版本 solver.py 兼容的接口，内部使用新的
    UniversalBiasManager 实现所有功能。

    用法示例：
        # 方式1：使用新偏置系统
        from nsgablack.bias import BiasModule, DiversityBias, ConstraintBias

        bias = BiasModule()
        bias.add(DiversityBias(weight=0.2))
        bias.add(ConstraintBias(weight=2.0))

        # 配置到求解器
        solver.bias_module = bias
        solver.enable_bias = True

        # 方式2：从 UniversalBiasManager 创建
        from nsgablack.bias import UniversalBiasManager
        manager = UniversalBiasManager()
        manager.add_algorithmic_bias(DiversityBias(weight=0.2))

        bias = BiasModule.from_universal_manager(manager)
    """

    def __init__(self):
        """初始化偏置模块"""
        self._manager: Optional[UniversalBiasManager] = None
        if NEW_SYSTEM_AVAILABLE and UniversalBiasManagerImpl is not None:
            self._manager = UniversalBiasManagerImpl()
        else:
            self._legacy_biases: List[Any] = []

        # 运行时缓存与上下文复用
        self._context_cache = None
        self.cache_enabled = True
        self.cache_max_items = 128
        self._bias_cache: "OrderedDict[Any, float]" = OrderedDict()
        self._bias_cache_version = 0

        # 参数变更回调（用于缓存失效）
        self._param_change_handler = self._on_bias_param_change

        # 兼容层弃用提示去重
        self._legacy_warnings: Set[str] = set()
        if not NEW_SYSTEM_AVAILABLE:
            self._warn_legacy(
                "legacy_mode",
                "BiasModule 正在使用旧兼容模式（未检测到新偏置系统）。"
                "该兼容模式将在未来版本移除，请迁移到 UniversalBiasManager。",
            )

        # 兼容属性
        self.enable = True
        self._name = "BiasModule"

        # 历史最优跟踪（用于部分偏置/分析场景）
        self.history_best_x = None
        self.history_best_f = float("inf")

    def _warn_legacy(self, key: str, message: str) -> None:
        if key in self._legacy_warnings:
            return
        warnings.warn(message, DeprecationWarning, stacklevel=3)
        self._legacy_warnings.add(key)

    @classmethod
    def from_universal_manager(cls, manager: UniversalBiasManager) -> 'BiasModule':
        """
        从现有的 UniversalBiasManager 创建 BiasModule

        Args:
            manager: 已配置的 UniversalBiasManager 实例

        Returns:
            BiasModule: 配置好的偏置模块
        """
        bias_module = cls()
        bias_module._manager = manager
        bias_module._register_existing_bias_callbacks()
        return bias_module

    def add(self, bias, weight: float = 1.0, name: Optional[str] = None) -> bool:
        """
        添加偏置（兼容接口）

        Args:
            bias: 偏置对象或配置字典
            weight: 偏置权重
            name: 可选的偏置名称

        Returns:
            是否成功添加
        """
        if not NEW_SYSTEM_AVAILABLE:
            print("Warning: New bias system not available, using legacy mode")
            self._warn_legacy(
                "legacy_mode",
                "BiasModule 正在使用旧兼容模式（未检测到新偏置系统）。"
                "该兼容模式将在未来版本移除，请迁移到 UniversalBiasManager。",
            )
            self._legacy_biases.append((bias, weight))
            return True

        # 处理不同类型的偏置输入
        if isinstance(bias, dict):
            # 从字典创建偏置
            bias_type = bias.get('type', 'algorithmic')
            bias_name = name or bias.get('name', 'unnamed_bias')
            bias_params = bias.get('params', {})

            # 创建偏置对象
            if hasattr(self._manager, f'add_{bias_type}_bias'):
                # 如果有特定的添加方法，使用它
                bias_obj = self._create_bias_from_dict(bias_type, bias_params)
                if bias_obj is not None:
                    added = self._manager.add_algorithmic_bias(bias_obj)
                    if added:
                        self._register_bias_callbacks(bias_obj)
                        self._bump_cache_version()
                    return added
            else:
                # 否则直接添加
                added = self._manager.add_algorithmic_bias(bias)
                if added:
                    self._register_bias_callbacks(bias)
                    self._bump_cache_version()
                return added

        elif BiasInterfaceImpl is not None and isinstance(bias, BiasInterfaceImpl):
            # 添加偏置对象（算法或领域偏置）
            if AlgorithmicBiasImpl is not None and isinstance(bias, AlgorithmicBiasImpl):
                added = self._manager.add_algorithmic_bias(bias)
                if added:
                    self._register_bias_callbacks(bias)
                    self._bump_cache_version()
                return added
            if DomainBiasImpl is not None and isinstance(bias, DomainBiasImpl):
                added = self._manager.add_domain_bias(bias)
                if added:
                    self._register_bias_callbacks(bias)
                    self._bump_cache_version()
                return added
            added = self._manager.add_algorithmic_bias(bias)
            if added:
                self._register_bias_callbacks(bias)
                self._bump_cache_version()
            return added

        elif callable(bias):
            # 函数式偏置：包装为 DomainBias
            from .domain import RuleBasedBias
            rule_bias = RuleBasedBias(
                rule_func=bias,
                weight=weight,
                name=name or "functional_bias"
            )
            added = self._manager.add_domain_bias(rule_bias)
            if added:
                self._register_bias_callbacks(rule_bias)
                self._bump_cache_version()
            return added

        else:
            print(f"Warning: Unsupported bias type: {type(bias)}")
            return False

    def add_penalty(self, penalty_func: Callable, weight: float = 1.0, name: str = "penalty"):
        """
        添加惩罚函数（兼容接口）

        Args:
            penalty_func: 惩罚函数
            weight: 权重
            name: 名称
        """
        raise AttributeError(
            "BiasModule.add_penalty 已移除。请改用 bias.add(CallableBias(..., mode='penalty'))。"
        )

    def add_reward(self, reward_func: Callable, weight: float = 1.0, name: str = "reward"):
        """
        添加奖励函数（兼容接口）

        Args:
            reward_func: 奖励函数
            weight: 权重
            name: 名称
        """
        raise AttributeError(
            "BiasModule.add_reward 已移除。请改用 bias.add(CallableBias(..., mode='reward'))。"
        )

    def compute_bias(self, x: np.ndarray, objective_value: float,
                    individual_id: Optional[Any] = None,
                    context: Optional[Dict[str, Any]] = None) -> float:
        """
        计算偏置值（兼容接口）

        这是 solver.py 调用的核心方法。

        Args:
            x: 决策变量
            objective_value: 原始目标值
            individual_id: 个体ID
            context: 上下文信息

        Returns:
            偏置后的目标值
        """
        if isinstance(individual_id, dict) and context is None:
            context = individual_id
            individual_id = 0

        if context is None:
            context = {}
        context.setdefault("constraints", [])
        context.setdefault("generation", 0)

        biased_value = objective_value

        if NEW_SYSTEM_AVAILABLE and self._manager is not None and OptimizationContextImpl is not None:
            x_bytes = None
            if self.cache_enabled:
                try:
                    x_bytes = np.asarray(x).tobytes()
                except Exception:
                    x_bytes = None

            biased_value = self._compute_new_system_bias(
                x=x,
                objective_value=objective_value,
                individual_id=int(individual_id) if individual_id is not None else 0,
                context=context,
                _x_bytes=x_bytes,
            )

        if objective_value < self.history_best_f:
            self.history_best_f = float(objective_value)
            self.history_best_x = np.asarray(x, dtype=float).copy()

        return biased_value

    def compute_bias_vector(
        self,
        x: np.ndarray,
        objective_values: np.ndarray,
        individual_id: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """一次性对同一个个体的多个目标值应用 bias（减少重复开销）。

        返回与 objective_values 形状一致的一维数组。
        """
        if context is None:
            context = {}
        context.setdefault("constraints", [])
        context.setdefault("generation", 0)

        obj_arr = np.asarray(objective_values, dtype=float).reshape(-1)
        out = obj_arr.copy()

        ind_id = int(individual_id) if individual_id is not None else 0

        x_bytes = None
        if self.cache_enabled:
            try:
                x_bytes = np.asarray(x).tobytes()
            except Exception:
                x_bytes = None

        if NEW_SYSTEM_AVAILABLE and self._manager is not None and OptimizationContextImpl is not None:
            for k in range(out.size):
                out[k] = self._compute_new_system_bias(
                    x=x,
                    objective_value=float(out[k]),
                    individual_id=ind_id,
                    context=context,
                    _x_bytes=x_bytes,
                )

        # 与逐目标调用保持近似兼容：以最小原始目标值更新历史最优
        try:
            best_obj = float(np.min(obj_arr))
        except Exception:
            best_obj = float(obj_arr[0]) if obj_arr.size else float("inf")
        if best_obj < self.history_best_f:
            self.history_best_f = best_obj
            self.history_best_x = np.asarray(x, dtype=float).copy()

        return out

    def compute_bias_batch(
        self,
        xs: np.ndarray,
        objectives: np.ndarray,
        individual_ids: Optional[np.ndarray] = None,
        contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> np.ndarray:
        """批量应用 bias。

        - xs: (N, D)
        - objectives: (N, M)
        - contexts: 可选，长度 N
        """
        xs_arr = np.asarray(xs)
        obj_arr = np.asarray(objectives, dtype=float)
        if obj_arr.ndim == 1:
            obj_arr = obj_arr.reshape(-1, 1)

        n = obj_arr.shape[0]
        out = obj_arr.copy()
        if individual_ids is None:
            individual_ids = np.arange(n)

        for i in range(n):
            ctx = contexts[i] if contexts is not None else None
            out[i] = self.compute_bias_vector(xs_arr[i], out[i], individual_id=individual_ids[i], context=ctx)

        return out

    def _compute_new_system_bias(self, x: np.ndarray, objective_value: float,
                                 individual_id: int, context: Dict[str, Any],
                                 _x_bytes: Optional[bytes] = None) -> float:
        cache_key = None
        if self.cache_enabled:
            try:
                cache_key = (
                    individual_id,
                    float(objective_value),
                    _x_bytes if _x_bytes is not None else np.asarray(x).tobytes(),
                    context.get('generation', 0),
                    self._bias_cache_version,
                )
                cached = self._bias_cache.get(cache_key)
                if cached is not None:
                    self._bias_cache.move_to_end(cache_key)
                    return cached
            except (TypeError, ValueError, AttributeError) as e:
                logger.warning("Bias cache key creation failed; bypass cache: %s", e)
                cache_key = None
            except Exception:
                logger.error("Unexpected error creating bias cache key", exc_info=True)
                cache_key = None

        opt_context = self._get_or_update_context(
            x=x,
            objective_value=objective_value,
            individual_id=individual_id,
            context=context,
        )
        if opt_context is None:
            return objective_value

        total_bias = 0.0
        if hasattr(self._manager, 'algorithmic_manager'):
            for bias in self._manager.algorithmic_manager.biases.values():
                if getattr(bias, 'enabled', True):
                    bias_value = bias.compute(x, opt_context)
                    total_bias += bias_value * getattr(bias, 'weight', 1.0)

        if hasattr(self._manager, 'domain_manager'):
            for bias in self._manager.domain_manager.biases.values():
                if getattr(bias, 'enabled', True):
                    bias_value = bias.compute(x, opt_context)
                    total_bias += bias_value * getattr(bias, 'weight', 1.0)

        biased_value = objective_value + total_bias
        if cache_key is not None:
            if len(self._bias_cache) >= self.cache_max_items:
                self._bias_cache.popitem(last=False)
            self._bias_cache[cache_key] = biased_value

        return biased_value

    def _get_or_update_context(self, x: np.ndarray, objective_value: float, individual_id: int, context: Dict[str, Any]):
        """复用或创建 OptimizationContext，减少重复分配。"""
        if OptimizationContextImpl is None:
            return None

        # Allow capability layers (plugins/adapters/solvers) to attach additional metrics
        # without changing the bias system API surface.
        extra_metrics = context.get("metrics", {})
        if not isinstance(extra_metrics, dict):
            extra_metrics = {}

        if self._context_cache is None:
            try:
                problem_data = context.get('problem_data', {})
                if not isinstance(problem_data, dict):
                    problem_data = {}
                else:
                    problem_data = dict(problem_data)
                # Keep a canonical place for constraint reports to support rule-based biases/plugins.
                if "constraints" in context:
                    problem_data.setdefault("constraints", context.get("constraints", []))

                metrics = {
                    'objective_value': objective_value,
                    'individual_id': individual_id,
                    'constraint_violation': context.get('constraint_violation', 0.0),
                }
                metrics.update(extra_metrics)
                self._context_cache = OptimizationContextImpl(
                    generation=context.get('generation', 0),
                    individual=x,
                    population=context.get('population', []),
                    metrics=metrics,
                    history=context.get('history', []),
                    problem_data=problem_data,
                )
            except Exception:
                return None

        try:
            # 使用浅拷贝避免跨个体污染，同时复用已分配对象以减轻分配开销
            ctx = copy.copy(self._context_cache)
            setattr(ctx, 'generation', context.get('generation', 0))
            setattr(ctx, 'individual', x)
            setattr(ctx, 'population', context.get('population', []))
            metrics = {
                'objective_value': objective_value,
                'individual_id': individual_id,
                'constraint_violation': context.get('constraint_violation', 0.0),
            }
            metrics.update(extra_metrics)
            setattr(ctx, 'metrics', metrics)
            try:
                setattr(ctx, 'history', context.get('history', []))
                problem_data = context.get('problem_data', {})
                if not isinstance(problem_data, dict):
                    problem_data = {}
                else:
                    problem_data = dict(problem_data)
                if "constraints" in context:
                    problem_data.setdefault("constraints", context.get("constraints", []))
                setattr(ctx, 'problem_data', problem_data)
            except Exception:
                pass
            return ctx
        except Exception:
            logger.error("Failed to prepare optimization context", exc_info=True)
            return None

    def enable_all(self):
        """启用所有偏置"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            if hasattr(self._manager, 'enable_all'):
                self._manager.enable_all()
            else:
                # 分别启用算法和领域偏置
                if hasattr(self._manager, 'algorithmic_manager'):
                    self._manager.algorithmic_manager.enable_all()
                if hasattr(self._manager, 'domain_manager'):
                    self._manager.domain_manager.enable_all()

    def disable_all(self):
        """禁用所有偏置"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            if hasattr(self._manager, 'disable_all'):
                self._manager.disable_all()
            else:
                # 分别禁用算法和领域偏置
                if hasattr(self._manager, 'algorithmic_manager'):
                    self._manager.algorithmic_manager.disable_all()
                if hasattr(self._manager, 'domain_manager'):
                    self._manager.domain_manager.disable_all()

    def get_bias(self, name: str):
        """获取指定偏置"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            # 尝试从算法偏置管理器获取
            if hasattr(self._manager, 'algorithmic_manager'):
                bias = self._manager.algorithmic_manager.get_bias(name)
                if bias is not None:
                    return bias
            # 尝试从领域偏置管理器获取
            if hasattr(self._manager, 'domain_manager'):
                bias = self._manager.domain_manager.get_bias(name)
                if bias is not None:
                    return bias
        return None

    def remove_bias(self, name: str) -> bool:
        """移除指定偏置"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            # 尝试从算法偏置管理器移除
            if hasattr(self._manager, 'algorithmic_manager'):
                if self._manager.algorithmic_manager.remove_bias(name):
                    self._bump_cache_version()
                    return True
            # 尝试从领域偏置管理器移除
            if hasattr(self._manager, 'domain_manager'):
                if self._manager.domain_manager.remove_bias(name):
                    self._bump_cache_version()
                    return True
        return False

    def list_biases(self) -> List[str]:
        """列出所有偏置"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            # UniversalBiasManager 没有直接的 list_biases 方法
            # 需要从 algorithmic_manager 和 domain_manager 获取
            biases = []
            if hasattr(self._manager, 'algorithmic_manager'):
                biases.extend(self._manager.algorithmic_manager.list_biases())
            if hasattr(self._manager, 'domain_manager'):
                biases.extend(self._manager.domain_manager.list_biases())
            return biases
        return []

    def to_universal_manager(self) -> Optional[UniversalBiasManager]:
        """
        转换为 UniversalBiasManager

        Returns:
            UniversalBiasManager 实例
        """
        return self._manager

    @property
    def algorithmic_manager(self):
        """获取算法偏置管理器（兼容属性）"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            return self._manager.algorithmic_manager
        return None

    @property
    def domain_manager(self):
        """获取领域偏置管理器（兼容属性）"""
        if NEW_SYSTEM_AVAILABLE and self._manager:
            return self._manager.domain_manager
        return None

    def _create_bias_from_dict(self, bias_type: str, params: Dict[str, Any]):
        """从字典创建偏置对象"""
        if not NEW_SYSTEM_AVAILABLE:
            return None

        try:
            # 导入常用偏置类
            from .algorithmic import (
                DiversityBias, ConvergenceBias, SimulatedAnnealingBias,
                TabuSearchBias, PrecisionBias
            )
            from .domain import ConstraintBias

            bias_map = {
                'diversity': (DiversityBias, params),
                'convergence': (ConvergenceBias, params),
                'simulated_annealing': (SimulatedAnnealingBias, params),
                'tabu_search': (TabuSearchBias, params),
                'precision': (PrecisionBias, params),
                'constraint': (ConstraintBias, params),
            }

            if bias_type in bias_map:
                bias_class, bias_params = bias_map[bias_type]
                return bias_class(**bias_params)
            else:
                print(f"Warning: Unknown bias type: {bias_type}")
                return None

        except ImportError as e:
            print(f"Warning: Could not import bias class: {e}")
            return None

    def clear(self):
        """清空所有偏置并重置历史信息。"""
        if NEW_SYSTEM_AVAILABLE and self._manager is not None:
            try:
                algo_mgr = getattr(self._manager, "algorithmic_manager", None)
                dom_mgr = getattr(self._manager, "domain_manager", None)
                if algo_mgr is not None and hasattr(algo_mgr, "biases"):
                    algo_mgr.biases.clear()
                if dom_mgr is not None and hasattr(dom_mgr, "biases"):
                    dom_mgr.biases.clear()
            except Exception:
                pass
        self.history_best_x = None
        self.history_best_f = float("inf")
        self._bump_cache_version()

    def __repr__(self):
        """字符串表示"""
        return f"BiasModule(biases={self.list_biases()}, enabled={self.enable})"

    # 缓存与版本管理
    def clear_cache(self):
        """清空偏置缓存。"""
        self._bias_cache.clear()

    def _bump_cache_version(self):
        """当偏置集合变化时，增加版本并清缓存。"""
        self._bias_cache_version += 1
        self._bias_cache.clear()

    # 内部工具：注册偏置参数变更回调，用于触发缓存失效
    def _register_bias_callbacks(self, bias: Any):
        if bias is None:
            return
        try:
            register = getattr(bias, "register_param_change_callback", None)
            if callable(register):
                register(self._param_change_handler)
        except Exception:
            logger.debug("Failed to register param change callback for bias %s", getattr(bias, "name", "<unknown>"), exc_info=True)

    def _register_existing_bias_callbacks(self):
        if not (NEW_SYSTEM_AVAILABLE and self._manager):
            return
        for mgr in (
            getattr(self._manager, "algorithmic_manager", None),
            getattr(self._manager, "domain_manager", None),
        ):
            if mgr is None:
                continue
            for bias in getattr(mgr, "biases", {}).values():
                self._register_bias_callbacks(bias)

    def _on_bias_param_change(self, bias: Any):
        # 偏置启用/禁用或权重调整时让缓存失效
        self._bump_cache_version()


def proximity_reward(x: np.ndarray, best_x: np.ndarray) -> float:
    """Reward closer solutions to the current best."""
    distance = float(np.linalg.norm(np.asarray(x) - np.asarray(best_x)))
    return 1.0 / (1.0 + distance)


def improvement_reward(current_f: float, previous_f: float) -> float:
    """Reward improvements in objective value."""
    return max(0.0, float(previous_f) - float(current_f))


# 便捷函数
def create_bias_module() -> BiasModule:
    """创建并返回一个预配置的 BiasModule"""
    return BiasModule()


def from_universal_manager(manager: UniversalBiasManager) -> BiasModule:
    """从 UniversalBiasManager 创建 BiasModule"""
    return BiasModule.from_universal_manager(manager)
