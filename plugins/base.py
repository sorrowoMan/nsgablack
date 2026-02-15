"""
鎻掍欢绯荤粺鍩虹鏋舵瀯
"""

from abc import ABC
from typing import Optional, Dict, Any
import time
import traceback
import warnings


class Plugin(ABC):
    """
    鎻掍欢鍩虹被

    鎵€鏈夋彃浠堕兘搴旂户鎵挎绫诲苟瀹炵幇鐩稿簲鐨勬柟娉?
    """

    def __init__(self, name: str, solver=None, priority: int = 0):
        """
        鍒濆鍖栨彃浠?

        Args:
            name: 鎻掍欢鍚嶇О
            solver: 姹傝В鍣ㄥ疄渚嬶紙鍙€夛紝绋嶅悗鍙互attach锛?
            priority: 鎻掍欢浼樺厛绾э紙鏁板€艰秺澶т紭鍏堢骇瓒婇珮锛?
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

        # Context contract (optional; for compatibility the defaults are empty).
        # Declare as class attributes in subclasses when needed.
        # - context_requires: fields this plugin expects in context
        # - context_provides: fields this plugin writes to context
        # - context_mutates: fields this plugin may overwrite
        # - context_cache: fields considered cache (non-replayable)

    # Optional contract metadata (class-level defaults)
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = None

    def get_context_contract(self) -> Dict[str, Any]:
        return {
            "requires": getattr(self, "context_requires", ()),
            "provides": getattr(self, "context_provides", ()),
            "mutates": getattr(self, "context_mutates", ()),
            "cache": getattr(self, "context_cache", ()),
            "notes": getattr(self, "context_notes", None),
        }

    def attach(self, solver):
        """闄勫姞鍒版眰瑙ｅ櫒"""
        self.solver = solver

    def detach(self):
        """浠庢眰瑙ｅ櫒鍒嗙"""
        self.solver = None

    def enable(self):
        """鍚敤鎻掍欢"""
        self.enabled = True

    def disable(self):
        """绂佺敤鎻掍欢"""
        self.enabled = False

    def configure(self, **kwargs):
        """閰嶇疆鎻掍欢鍙傛暟"""
        self.config.update(kwargs)

    def get_config(self, key: str, default=None):
        """鑾峰彇閰嶇疆鍙傛暟"""
        return self.config.get(key, default)

    def on_solver_init(self, solver):
        """姹傝В鍣ㄥ垵濮嬪寲鏃惰皟鐢紙榛樿鏃犳搷浣滐紝渚夸簬蹇€熷紑鍙戯級銆?"""
        return None

    def on_population_init(self, population, objectives, violations):
        """绉嶇兢鍒濆鍖栧悗璋冪敤锛堥粯璁ゆ棤鎿嶄綔锛夈€?"""
        return None

    def on_generation_start(self, generation: int):
        """姣忎唬寮€濮嬫椂璋冪敤锛堥粯璁ゆ棤鎿嶄綔锛夈€?"""
        return None

    def on_generation_end(self, generation: int):
        """姣忎唬缁撴潫鏃惰皟鐢紙榛樿鏃犳搷浣滐級銆?"""
        return None

    def on_step(self, solver, generation: int):
        """绌虹櫧姹傝В鍣ㄦ瘡姝ュ洖璋冿紙榛樿鏃犳搷浣滐級銆?"""
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        """姹傝В鍣ㄧ粨鏉熸椂璋冪敤锛堥粯璁ゆ棤鎿嶄綔锛夈€?"""
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        """
        鍙€夛細杩斿洖鎻掍欢鐨勨€滅畻娉曡础鐚?琛屼负鎽樿鈥濄€?
        绾﹀畾锛?        - 宸ュ叿鍨嬫彃浠讹紙log/export/viz锛変繚鎸?is_algorithmic=False锛岃繑鍥?None銆?        - 绠楁硶鍨嬫彃浠讹紙elite/regions/閲嶅惎/绛涢€夌瓑锛夎缃?is_algorithmic=True锛屽彲杩斿洖绠€瑕?dict銆?        """
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
    鎻掍欢绠＄悊鍣?

    绠＄悊澶氫釜鎻掍欢鐨勭敓鍛藉懆鏈熷拰浜嬩欢鍒嗗彂
    """

    def __init__(self, short_circuit: bool = False, short_circuit_events: Optional[list] = None):
        self.plugins = []
        self.plugin_map = {}  # name -> plugin
        self.short_circuit = short_circuit
        self.short_circuit_events = set(short_circuit_events or [])
        self._solver = None

    def register(self, plugin: Plugin):
        """
        娉ㄥ唽鎻掍欢

        Args:
            plugin: 鎻掍欢瀹炰緥
        """
        if plugin.name in self.plugin_map:
            raise ValueError(f"Plugin '{plugin.name}' already registered")

        self.plugins.append(plugin)
        # 楂樹紭鍏堢骇鍦ㄥ墠锛屼繚鎸佸悓浼樺厛绾ф敞鍐岄『搴?
        self.plugins.sort(key=lambda p: p.priority, reverse=True)
        self.plugin_map[plugin.name] = plugin
        return plugin

    def unregister(self, plugin_name: str):
        """
        娉ㄩ攢鎻掍欢

        Args:
            plugin_name: 鎻掍欢鍚嶇О
        """
        if plugin_name not in self.plugin_map:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        plugin = self.plugin_map[plugin_name]
        self.plugins.remove(plugin)
        del self.plugin_map[plugin_name]

    def get(self, plugin_name: str) -> Optional[Plugin]:
        """
        鑾峰彇鎻掍欢

        Args:
            plugin_name: 鎻掍欢鍚嶇О

        Returns:
            鎻掍欢瀹炰緥锛屽鏋滀笉瀛樺湪鍒欒繑鍥濶one
        """
        return self.plugin_map.get(plugin_name)

    def enable(self, plugin_name: str):
        """鍚敤鎻掍欢"""
        plugin = self.get(plugin_name)
        if plugin:
            plugin.enable()

    def disable(self, plugin_name: str):
        """绂佺敤鎻掍欢"""
        plugin = self.get(plugin_name)
        if plugin:
            plugin.disable()

    def trigger(self, event_name: str, *args, **kwargs):
        """
        瑙﹀彂浜嬩欢

        Args:
            event_name: 浜嬩欢鍚嶇О
            *args: 浣嶇疆鍙傛暟
            **kwargs: 鍏抽敭瀛楀弬鏁?
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
                                f"Plugin '{plugin.name}' returned a non-None result for event "
                                f"'{event_name}' (ignored). Enable short_circuit and add the event "
                                "to short_circuit_events to allow returning values."
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
        """閫氱煡鎵€鏈夋彃浠讹細姹傝В鍣ㄥ垵濮嬪寲"""
        self._solver = solver
        for plugin in self.plugins:
            if plugin.enabled:
                plugin.attach(solver)
                plugin.on_solver_init(solver)

    def on_population_init(self, population, objectives, violations):
        """閫氱煡鎵€鏈夋彃浠讹細绉嶇兢鍒濆鍖?"""
        self.trigger('on_population_init', population, objectives, violations)

    def on_generation_start(self, generation: int):
        """閫氱煡鎵€鏈夋彃浠讹細浠ｅ紑濮?"""
        self.trigger('on_generation_start', generation)

    def on_generation_end(self, generation: int):
        """閫氱煡鎵€鏈夋彃浠讹細浠ｇ粨鏉?"""
        self.trigger('on_generation_end', generation)

    def on_step(self, solver, generation: int):
        """閫氱煡鎵€鏈夋彃浠讹細鍗曟锛堢┖鐧芥眰瑙ｅ櫒锛?"""
        self.trigger('on_step', solver, generation)

    def on_solver_finish(self, result: Dict[str, Any]):
        """閫氱煡鎵€鏈夋彃浠讹細姹傝В鍣ㄧ粨鏉?"""
        self.trigger('on_solver_finish', result)
        for plugin in self.plugins:
            if not plugin.enabled:
                continue

    def list_plugins(self, enabled_only: bool = False) -> list:
        """
        鍒楀嚭鎵€鏈夋彃浠?

        Args:
            enabled_only: 鏄惁鍙垪鍑哄惎鐢ㄧ殑鎻掍欢

        Returns:
            鎻掍欢鍒楄〃
        """
        if enabled_only:
            return [p for p in self.plugins if p.enabled]
        return self.plugins.copy()

    def clear(self):
        """娓呯┖鎵€鏈夋彃浠?"""
        self.plugins.clear()
        self.plugin_map.clear()

    def __len__(self):
        return len(self.plugins)

    def __repr__(self):
        enabled_count = sum(1 for p in self.plugins if p.enabled)
        return f"<PluginManager({len(self.plugins)} plugins, {enabled_count} enabled)>"
