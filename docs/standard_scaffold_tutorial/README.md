# 标准脚手架教程（nsgablack）

本教程遵循统一框架栈：

- `nsgablack` + `mlblack` 共享 Project / Case / Scaffold / L0 substrate。
- 编排能力属于 substrate，不属于任一语义层私有能力。
- 所有 Case 都从 `build_solver.py` / `run_solver.py` 解析；`.case kind`
  只区分 `solver` / `trainer` 的语义和结果投影。
- 每个 Case 只保留一个 `pipeline/main.py` 主入口，内部用 slot operator 组合。

## 推荐阅读顺序

1. `00_assembly_api_reference.md`
2. `01_create_and_run.md`
3. `02_component_configuration.md`
4. `03_orchestration_language.md`
5. `04_validation_catalog_and_evolution.md`
6. `05_cross_framework_coordination.md`
7. `06_l0_parallel_resource_patterns.md`
8. `07_nested_orchestration_standard.md`
9. `08_slot_kernel_minimal_spec.md`
10. `09_custom_adapter.md`
11. `10_custom_bias.md`
12. `11_custom_plugin_hooks.md`
13. `12_pipeline_orchestration_and_component_design.md`

## CLI + 模板 + 教程闭环

1. 用共享 scaffold CLI 创建 Case。
2. 用 `project add-component --kind ... --slot ...` 生成组件文件。
3. 在 `pipeline/main.py` 装配 slot spec + operator registry。
4. 用 `project doctor` 与 `run_project.py --check --build-check` 验证。

两框架流程一致，差异在语义层：

- `nsgablack`：搜索/优化语义
- `mlblack`：ML 数据/模型语义
