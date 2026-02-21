# Case A（真实排产）- Plugin 逐行批注

来源：`examples/cases/production_scheduling/working_integrated_optimizer.py`

## A. 自定义进度插件（真实代码结构）
```python
class ConsoleProgressPlugin:  # 包装类：内部真实插件继承 nsgablack.plugins.Plugin
    def __init__(self, report_every: int = 10):  # 构造参数：每多少代打印一次
        from nsgablack.plugins import Plugin  # 延迟导入，避免启动时依赖顺序问题

        class _Impl(Plugin):  # 真正挂到 PluginManager 的实现
            context_requires = ()  # 不依赖 context 字段
            context_provides = ()  # 不提供字段
            context_mutates = ()  # 不修改字段
            context_cache = ()  # 不缓存
            context_notes = ("Console progress reporter; writes no context keys.",)  # 说明

            def __init__(self, report_every: int):  # 内部初始化
                super().__init__(name="console_progress")  # 插件名
                self.report_every = int(max(1, report_every))  # 防止 <=0
                self._t0 = None  # 总开始时间
                self._last_t = None  # 上次打印时间

            def on_solver_init(self, solver):  # solver 初始化钩子
                self._t0 = time.time()  # 记录开始时间
                self._last_t = self._t0  # 初始化 last_t

            def on_generation_end(self, generation: int):  # 每代结束钩子
                if generation % self.report_every != 0:  # 非打印代直接返回
                    return
                solver = getattr(self, "solver", None)  # 取绑定 solver
                if solver is None:  # 防御
                    return
                now = time.time()  # 当前时间
                dt = now - self._last_t if self._last_t is not None else 0.0  # 最近一步耗时
                self._last_t = now  # 更新时间戳
                best = getattr(solver, "best_objective", None)  # 读取当前最优
                print(f"[step {generation:04d}] last_step={dt:6.2f}s best={best}")  # 控制台输出

        self._plugin = _Impl(report_every=report_every)  # 实例化内部插件

    def __getattr__(self, name):  # 代理属性访问
        return getattr(self._plugin, name)  # 转发给内部插件
```

## B. 真实排产里插件接线（build_multi_agent_solver）
```python
solver.add_plugin(ParetoArchivePlugin())  # 持续维护 Pareto 档案
solver.add_plugin(ConsoleProgressPlugin(report_every=args.report_every))  # 控制台进度输出
solver.add_plugin(BenchmarkHarnessPlugin(config=...))  # 跑实验记录（csv/json）
solver.add_plugin(ModuleReportPlugin(config=...))  # 组件清单与契约报告
solver.add_plugin(ProfilerPlugin(config=...))  # 性能剖析（可开关）
```

## 插件层边界（排产场景）
- 插件负责“可观测性/可审计/性能记录”。
- 插件不该接管优化过程，不改算法主决策。
