# Run Inspector 变更日志

> 目的：保证 UI 迭代与文档同步，避免“实现已变更但使用说明滞后”。

## 2026-02-17

- Context 页增加非模态字段小窗联动：`Providers` / `Consumers` / `Window`。
- 字段小窗支持组件契约查看（requires/provides/mutates/cache/notes）并附带 Catalog Intro。
- 字段小窗支持双击组件跳回主界面 Details。
- Context 页增加节流刷新与缓存，降低频繁切换时的抖动。
- Context 页异常从“仅控制台”升级为“UI 内可见错误提示 + 状态栏提示”。
- 增加 Context 流程最小回归测试（选择字段 -> 小窗刷新 -> 双击跳转）。

## 2026-02-28

- Run/Audit 视图新增 `Sequence` 卡片，用于查看交互顺序图（去重后的组件调用序列）。
- Run 完成后自动刷新 Sequence 卡片；History 选中时联动加载 Sequence。
- 新增 `SequenceGraphPlugin` 输出 `runs/<run_id>.sequence_graph.json` 供 UI 读取。
- Sequence 卡片新增 `Trie` 子标签，用前缀树视图展示共享路径与分支结构。
- Sequence 卡片新增 `Trace` 子标签，可查看带 `start/end/thread/task/span/parent` 的时序明细。
- Trace 子标签新增 `By Thread/Task` 聚合视图，便于快速定位并发热点与异常分组。

## 2026-03-01

- Run/Audit 视图新增 `Repro` 卡片，支持 `Load Last / Load File / Compare Current / Run By Bundle`。
- 每次 Run 结束后自动导出 `runs/<run_id>.repro_bundle.json`（schema: `repro_bundle` v1）。
- Repro 比对结果输出 `BLOCKER/WARN/INFO`，用于区分“不可重跑”与“可重跑但有漂移”。

## 维护规则

- 每次 UI 行为变更，至少追加一条变更日志。
- 日志必须写清：入口位置、行为变化、用户可见影响。
- 若行为影响文档步骤，同步更新 `docs/user_guide/RUN_INSPECTOR.md`。
