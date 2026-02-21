# Case B（TSP）- Plugin 逐行批注

参考：`my_project/plugins/example_plugin.py`（GenerationHeartbeatPlugin）

```python
class GenerationHeartbeatPlugin(Plugin):  # 心跳插件：验证插件接入和 context 投影
    context_requires = (KEY_GENERATION,)  # 依赖 generation
    context_provides = ("project.heartbeat.count", "project.heartbeat.last_generation")  # 提供两个字段
    context_mutates = ("project.heartbeat.count", "project.heartbeat.last_generation")  # 会更新这两个字段
    context_cache = ()  # 不缓存
    context_notes = ("Write heartbeat counters to context for inspector checks.",)  # 说明

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:  # 初始化
        super().__init__(name="project_heartbeat")  # 插件名
        self.interval = max(1, int(interval))  # 触发间隔
        self.verbose = bool(verbose)  # 是否打印
        self._hits = 0  # 命中次数
        self._last_generation = 0  # 最后一次命中代数

    def on_generation_end(self, generation: int) -> None:  # 每代结束
        generation = int(generation)  # 统一类型
        if generation % self.interval != 0:  # 非命中代直接返回
            return
        self._hits += 1  # 计数+1
        self._last_generation = generation  # 更新最后命中代
        if self.verbose:  # 控制台输出
            print(f"[heartbeat] gen={generation} hits={self._hits}")

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:  # 构建 context 时注入字段
        context["project.heartbeat.count"] = int(self._hits)  # 注入心跳次数
        context["project.heartbeat.last_generation"] = int(self._last_generation)  # 注入最后代数
        return context  # 返回更新后的 context
```

## 重点
- 这是最适合“先验证插件链路是否通”的插件。
- Run Inspector 的 Context 页可直接看到这两个字段。
