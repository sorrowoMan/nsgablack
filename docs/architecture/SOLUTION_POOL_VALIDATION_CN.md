# 解池实现与验收

日期：2026-10-13。仓库：nsgablack；共享 Snapshot/事务继续使用 BlackBase，本轮不修改共享底座或 MLBlack。

结果：**288 项不同的相关测试通过；仓库严格 Doctor 和新 Case 装配 Doctor 均为 0 error / 0 warning；正式 Project 运行成功。** 这是指定边界的实现与行为验收，不是算法优越性或任意组件组合的证明。

主要源码：SolutionPool；Solver 候选帮助函数与共享步骤事务；PoolSearchAdapter；NSGA-II/III 池输入；SA 显式搜索重启；候选 provenance 与 manifest；Doctor 运行契约检查；Catalog 双 profile；标准 Case 与中文契约。

## 回归范围与命令

主回归 245 项，运行 267.18 秒，5 条测试警告，没有失败。包括完整 200→100×2→停滞唤醒→返回竞争、第二个子算法失败的整组回滚、零接纳后重试、部分种子补齐、嵌套组合、必需 checkpoint 状态、manifest 冻结、原始反馈与身份来源；还包括既有 Unit 成员、repair、SA、语义候选、约束接纳、Bias、步骤事务、并行求值和 Solver 优化回归。

```powershell
python -m pytest tests/test_solution_pool.py tests/test_pool_search_adapter.py tests/test_proposal_repair.py tests/test_sa_adapter.py tests/test_candidate_population_semantics.py tests/test_runtime_contract_refinement.py tests/test_checkpoint_resume_plugin.py tests/test_adapter_step_transactions.py tests/test_evaluation_acceptance.py tests/test_bias_acceptance_boundary.py tests/test_composite_population_authority.py tests/test_unit_member_composition.py tests/test_population_member_operations.py tests/test_context_key_alignment.py tests/test_context_contracts_semantic.py tests/test_catalog_context_contracts.py tests/test_solver.py tests/test_parallel_integration.py tests/test_snapshot_store.py -q --disable-warnings --maxfail=2 --junitxml=artifacts/audit/solution_pool_20261013/tests.xml
```

Doctor 继承检查与脚手架另有 43 项不同测试通过（4.87 秒）。检查真实 Python C3 顺序上的继承恢复接口；子类将 setter 覆盖为 None 时仍拒绝；状态声明不能冒充 context 声明。

```powershell
python -m pytest tests/test_source_contract_resolver.py tests/test_project_scaffold_registration_guide.py -q --disable-warnings --maxfail=1 --junitxml=artifacts/audit/solution_pool_20261013/doctor_tests.xml
```

开发过程发现的候选交接 metadata/token 冲突、CandidateBatch 重建后 provenance 丢失、零接纳输入 ID 失效、旧 Bias 字符串键和 Doctor 继承误报均已修正。上述通过结果来自修正后的实际执行；同一测试在多次复测中不重复计入 288。

## Doctor 和可发现性

```powershell
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json
python -m nsgablack project doctor --path examples/cases/solution_pool --strict --build --format json
```

仓库结果：0 error、0 warning、171 info。该命令覆盖声明、源码面、已发现 Case 的结构与主干 Catalog；**没有对全部 Case 执行 --build**。覆盖记录中仍存在跳过项，不能解释成全仓算法或所有运行后端已经通过。

新 Project 结果：0 error、0 warning、9 info；case-registry 和 case-build 都 completed。装配检查实际执行 builder，不执行搜索。

以 `get_catalog(refresh=True, profile=...)` 分别核验六个新增键：adapter.pool_search、tool.solution_pool、tool.solution_ref、tool.solution_stamp 在 default 与 framework-core 都可发现；doc.architecture.solution_pool、example.solution_pool 仅在 default 可发现。检查只读，不同步任何数据库。

本机 JSON 与 JUnit 原始输出保存在 `artifacts/audit/solution_pool_20261013/`（生成产物不提交 Git）。

## 正式 Project 执行

```powershell
python examples/cases/solution_pool/cases/pool_search/run_solver.py --check
python examples/cases/solution_pool/run_project.py
```

独立 Case 显示 `assembly ok`、adapter=pool_search、无额外 Plugin/Provider。Project 运行 exit=0、status=ok，Case succeeded，逻辑步骤/generation=7、求值次数=48，按正式 L0 使用 threads=1、workers=1、无 GPU，resource_binding.current=true。

运行记录：`examples/cases/solution_pool/.blackbase/runs/20261013T033810Z-3046aeb4cd/manifest.json`。小规模示例准备 8 个候选、两边各 4 个；完整 200/100/100 规模来自行为测试，不把小示例冒充该规模的运行结果。

## 本轮边界

所有 Adapter 的正式候选提案经共同控制面登记到池；NSGA-II/III 与 SA 明确支持本轮池输入/重启组合。其他 Adapter 还需按契约接入具体输入模式。内置 Unit 继续保存数值工作投影，本轮没有把所有算法内部改成 ref-only。

池保存公开候选历史，但不自动选优、去重、复用评估或裁剪公开历史。私有草稿退出索引，物理 Snapshot 清理仍由共享存储负责；长期运行的历史/manifest 存储规模和更多后端尚未作性能验收。

标准示例验证阶段和事务；停滞指标不证明局部最优，启动 SA 也不保证获得性能提升。跨 Case 传输、CPU 并行与 L0 继续由 BlackBase 承担，MLBlack 内部运行不在本轮测试范围。
