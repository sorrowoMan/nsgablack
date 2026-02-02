"""
插件系统基础架构
"""

from abc import ABC
from typing import Optional, Dict, Any
import time
import traceback
import warnings


class Plugin(ABC):
    """
    插件基类

    所有插件都应继承此类并实现相应的方法
    """

    def __init__(self, name: str, solver=None, priority: int = 0):
        """
        初始化插件

        Args:
            name: 插件名称
            solver: 求解器实例（可选，稍后可以attach）
            priority: 插件优先级（数值越大优先级越高）
        """
        self.name = name
        self.solver = solver
        self.enabled = True
        self.config = {}
        self.priority = priority
        # Optional semantics:
        # - is_algorithmic=True: plugin contributes to search behavior and should be audited.
        # - get_report(): returns a small dict for ModuleReportPlugin to persist.
        self.is_algorithmic = False
        self._profile = {"total_s": 0.0, "events": {}}

    def attach(self, solver):
        """附加到求解器"""
        self.solver = solver

    def detach(self):
        """从求解器分离"""
        self.solver = None

    def enable(self):
        """启用插件"""
        self.enabled = True

    def disable(self):
        """禁用插件"""
        self.enabled = False

    def configure(self, **kwargs):
        """配置插件参数"""
        self.config.update(kwargs)

    def get_config(self, key: str, default=None):
        """获取配置参数"""
        return self.config.get(key, default)

    def on_solver_init(self, solver):
        """求解器初始化时调用（默认无操作，便于快速开发）。"""
        return None

    def on_population_init(self, population, objectives, violations):
        """种群初始化后调用（默认无操作）。"""
        return None

    def on_generation_start(self, generation: int):
        """每代开始时调用（默认无操作）。"""
        return None

    def on_generation_end(self, generation: int):
        """每代结束时调用（默认无操作）。"""
        return None

    def on_step(self, solver, generation: int):
        """空白求解器每步回调（默认无操作）。"""
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束时调用（默认无操作）。"""
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        """
        可选：返回插件的“算法贡献/行为摘要”。

        约定：
        - 工具型插件（log/export/viz）保持 is_algorithmic=False，返回 None。
        - 算法型插件（elite/regions/重启/筛选等）设置 is_algorithmic=True，可返回简要 dict。
        """
        if not bool(getattr(self, "is_algorithmic", False)):
            return None
        try:
            return {"config": dict(self.config)}
        except Exception:
            return {"config": {}}

    def __repr__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__}({self.name}, {status})>"


class PluginManager:
    """
    插件管理器

    管理多个插件的生命周期和事件分发
    """

    def __init__(self, short_circuit: bool = False, short_circuit_events: Optional[list] = None):
        self.plugins = []
        self.plugin_map = {}  # name -> plugin
        self.short_circuit = short_circuit
        self.short_circuit_events = set(short_circuit_events or [])
        self._solver = None

    def register(self, plugin: Plugin):
        """
        注册插件

        Args:
            plugin: 插件实例
        """
        if plugin.name in self.plugin_map:
            raise ValueError(f"Plugin '{plugin.name}' already registered")

        self.plugins.append(plugin)
        # 高优先级在前，保持同优先级注册顺序
        self.plugins.sort(key=lambda p: p.priority, reverse=True)
        self.plugin_map[plugin.name] = plugin
        return plugin

    def unregister(self, plugin_name: str):
        """
        注销插件

        Args:
            plugin_name: 插件名称
        """
        if plugin_name not in self.plugin_map:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        plugin = self.plugin_map[plugin_name]
        self.plugins.remove(plugin)
        del self.plugin_map[plugin_name]

    def get(self, plugin_name: str) -> Optional[Plugin]:
        """
        获取插件

        Args:
            plugin_name: 插件名称

        Returns:
            插件实例，如果不存在则返回None
        """
        return self.plugin_map.get(plugin_name)

    def enable(self, plugin_name: str):
        """启用插件"""
        plugin = self.get(plugin_name)
        if plugin:
            plugin.enable()

    def disable(self, plugin_name: str):
        """禁用插件"""
        plugin = self.get(plugin_name)
        if plugin:
            plugin.disable()

    def trigger(self, event_name: str, *args, **kwargs):
        """
        触发事件

        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        should_short_circuit = self.short_circuit and event_name in self.short_circuit_events

        for plugin in self.plugins:
            if not plugin.enabled:
                continue

            handler = getattr(plugin, event_name, None)
            if handler and callable(handler):
                try:
                    t0 = time.time()
                    result = handler(*args, **kwargs)
                    dt = max(0.0, float(time.time() - t0))
                    prof = getattr(plugin, "_profile", None)
                    if isinstance(prof, dict):
                        prof["total_s"] = float(prof.get("total_s", 0.0) or 0.0) + dt
                        events = prof.get("events")
                        if not isinstance(events, dict):
                            events = {}
                            prof["events"] = events
                        events[event_name] = float(events.get(event_name, 0.0) or 0.0) + dt

                    if should_short_circuit and result is not None:
                        return result
                    if (not should_short_circuit) and result is not None:
                        warnings.warn(
                            (
                                f"Plugin '{plugin.name}' 在事件 '{event_name}' 返回了非 None 值（将被忽略）。"
                                "如需短路返回，请启用 short_circuit 并将该事件加入 short_circuit_events。"
                            ),
                            RuntimeWarning,
                            stacklevel=2,
                        )
                except Exception as e:
                    print(
                        f"[WARNING] Plugin {plugin.name} failed to handle {event_name}: {e}\n"
                        f"{traceback.format_exc()}"
                    )
            # allow return values for custom hooks via dispatch()

    def dispatch(self, event_name: str, *args, **kwargs):
        """
        Dispatch an event and return the last non-None value.
        """
        out = None
        for plugin in self.plugins:
            if not plugin.enabled:
                continue
            handler = getattr(plugin, event_name, None)
            if handler and callable(handler):
                try:
                    result = handler(*args, **kwargs)
                except Exception:
                    continue
                if result is not None:
                    out = result
        return out

    def on_solver_init(self, solver):
        """通知所有插件：求解器初始化"""
        self._solver = solver
        for plugin in self.plugins:
            if plugin.enabled:
                plugin.attach(solver)
                plugin.on_solver_init(solver)

    def on_population_init(self, population, objectives, violations):
        """通知所有插件：种群初始化"""
        self.trigger('on_population_init', population, objectives, violations)

    def on_generation_start(self, generation: int):
        """通知所有插件：代开始"""
        self.trigger('on_generation_start', generation)

    def on_generation_end(self, generation: int):
        """通知所有插件：代结束"""
        self.trigger('on_generation_end', generation)

    def on_step(self, solver, generation: int):
        """通知所有插件：单步（空白求解器）"""
        self.trigger('on_step', solver, generation)

    def on_solver_finish(self, result: Dict[str, Any]):
        """通知所有插件：求解器结束"""
        self.trigger('on_solver_finish', result)
        for plugin in self.plugins:
            if not plugin.enabled:
                continue

    def list_plugins(self, enabled_only: bool = False) -> list:
        """
        列出所有插件

        Args:
            enabled_only: 是否只列出启用的插件

        Returns:
            插件列表
        """
        if enabled_only:
            return [p for p in self.plugins if p.enabled]
        return self.plugins.copy()

    def clear(self):
        """清空所有插件"""
        self.plugins.clear()
        self.plugin_map.clear()

    def __len__(self):
        return len(self.plugins)

    def __repr__(self):
        enabled_count = sum(1 for p in self.plugins if p.enabled)
        return f"<PluginManager({len(self.plugins)} plugins, {enabled_count} enabled)>"
