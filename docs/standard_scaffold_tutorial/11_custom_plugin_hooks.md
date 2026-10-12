# 11. 定义 Plugin：从观察开始

只实现需要的钩子即可。下面统计物理尝试和逻辑提交，统计保留在插件实例，通过 get_report() 读取，不向 context 写入历史，也不申请决策或否决权限。

保存到 Case 的 `plugins/trace_audit_plugin.py`：

```python
from nsgablack.plugins.base import Plugin


class TraceAuditPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Observes attempts and commits; no shared context writes."

    def __init__(self, name="trace_audit_plugin"):
        super().__init__(name=name)
        self.attempts = 0
        self.committed = 0
        self.last_status = None

    def on_step_attempt_end(self, attempt, logical_step, outcome):
        self.attempts += 1
        self.last_status = outcome.status

    def on_generation_committed(self, generation, outcome):
        self.committed += 1

    def get_report(self):
        return {"attempts": self.attempts, "committed": self.committed,
                "last_status": self.last_status}
```

在原有 build_solver 创建 solver 后、返回之前加入：

```python
from .plugins.trace_audit_plugin import TraceAuditPlugin
solver.add_plugin(TraceAuditPlugin())
```

生命周期：初始化 → 每次物理尝试 start/end → 只有提交时的 generation 钩子 → finishing → teardown → finalization prepare → 原子发布 → finalized。失败、拒绝和空尝试仍计入 attempts，不计入 committed。

严格发布校验是另一种角色，必须声明否决权限。下面示例阻止发布非成功结果：

```python
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class SuccessPublicationGuard(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))

    def __init__(self):
        super().__init__(name="success_publication_guard")

    def on_solver_finalization_prepare(self, result):
        if result.get("status") != "ok":
            raise ValueError("Case result is not ready for successful publication")
```

prepare 在公开引用前执行，可以否决暂存产物；finalized 是发布后通知，不能撤销已提交结果。评估决定另须声明 `ParticipationContract(decides=("evaluation",))`。

自定义共享键写入 Project 或 Case 的 context_keys.json，并在组件 contract 声明读写；只共享轻量值或 Snapshot/Artifact 引用。完整 trace 使用框架 DecisionTrace/Snapshot。

验证命令：`python run_project.py --check --build-check` 和 `python run_project.py`。本章观察插件代码块直接参加 tests/test_scaffold_real_usage.py 的运行测试。
