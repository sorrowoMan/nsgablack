# NSGABlack 0.4 迁移说明

0.4.0 收紧 population authority：Plugin 只能观察和提供运行能力，不能在评估事务提交后
替换已提交 population。原先调用 `Plugin.commit_population_snapshot()` 的算法逻辑应迁移到
`AlgorithmAdapter.update()`、复合 Adapter，或 `EvaluationAcceptancePolicy`。

EliteRetention 的推荐装配方式为：

```python
from nsgablack.adapters import EliteRetentionAdapter, EliteRetentionConfig

solver.set_adapter(
    EliteRetentionAdapter(
        solver.adapter,
        EliteRetentionConfig(
            retention_probability=0.9,
            retention_ratio=0.1,
        ),
    )
)
```

旧的 `BasicElitePlugin` 与 `HistoricalElitePlugin` 导入和配置键仍可用。它们会发出包含
`remove_in=1.0.0` 的 `DeprecationWarning`，并把已有 Adapter 包装为事务型
`EliteRetentionAdapter`。兼容桥保留主要搜索意图，但不会恢复旧实现的 generation 后
authority 写入；依赖精确历史归档采样时机的代码应显式配置新的 Adapter 并重新验证结果。

共享 Snapshot/Evidence namespace 的部署还必须遵守 BlackBase 0.3.25 的协调升级门禁：
停止旧进程后整体升级，或为新版本使用新的 namespace。
