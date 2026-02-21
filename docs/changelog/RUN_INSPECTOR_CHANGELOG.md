# Run Inspector 变更日志

> 目的：保证 UI 迭代与文档同步，避免“实现已变更但使用说明滞后”。

## 2026-02-17

- Context 页增加非模态字段小窗联动：`Providers` / `Consumers` / `Window`。
- 字段小窗支持组件契约查看（requires/provides/mutates/cache/notes）并附带 Catalog Intro。
- 字段小窗支持双击组件跳回主界面 Details。
- Context 页增加节流刷新与缓存，降低频繁切换时的抖动。
- Context 页异常从“仅控制台”升级为“UI 内可见错误提示 + 状态栏提示”。
- 增加 Context 流程最小回归测试（选择字段 -> 小窗刷新 -> 双击跳转）。

## 维护规则

- 每次 UI 行为变更，至少追加一条变更日志。
- 日志必须写清：入口位置、行为变化、用户可见影响。
- 若行为影响文档步骤，同步更新 `docs/user_guide/RUN_INSPECTOR.md`。
