# 算法 Unit 示例项目

项目包含两个可独立运行的标准 Case：

- `candidate_search`：RandomProbeAdapter + CandidateUnitBuilder + build_unit 管线槽。
- `symbolic_beam`：JointBeamAdapter + BeamUnitBuilder + 稀疏候选问题管线。

运行 `python run_project.py --check --build-check` 查看实际装配；运行 `python run_project.py` 执行两个 Case。
跨 Case 资源授权由 Project L0 负责。每个 Case 的 build_solver 接收 ResourceContext，使用同一套正式运行入口。

旧 demo 通过兼容导入复用这里的实现。构建器不承担候选排序、Beam 截断、温度调度或目标评价。

候选 builder 声明 fresh/spawn/refresh 构建能力；Beam builder 声明 initialize/layout。
可用 `python -m nsgablack project doctor --path cases/candidate_search --strict --build` 或
`--path cases/symbolic_beam` 查看 Adapter 所需契约、实际 schema 和构建操作的对齐结果。
