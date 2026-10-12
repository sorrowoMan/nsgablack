# 候选 Unit Case

装配 RandomProbeAdapter、CandidateUnitBuilder 与 build_unit 管线槽；目标是二维球函数。
算法决定提出多少个候选，算法管线构建 Unit，问题管线负责初始化、变异与边界修复。

`adapter/` 同时收纳旧 demo 的 13 个轻量候选策略。旧文件保留兼容导入，
这些策略没有被误标为 DP、复杂优化器或完整种群算法。

验证：`python run_solver.py --check`。运行：`python run_solver.py`。
在 `component_overrides["unit_builder"]` 中替换构建器，可复用相同 Adapter。
