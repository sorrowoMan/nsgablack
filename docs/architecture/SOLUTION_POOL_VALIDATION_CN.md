# 解池实现与验收

最新补充：子池角色任务的实现与执行记录见文末「子池与多角色精修」；以下历史轮次保留原验证范围。

日期：2026-10-13。仓库：nsgablack；共享 Snapshot/事务继续使用 BlackBase，本轮不修改共享底座或 MLBlack。

首轮结果：**288 项不同的相关测试通过；仓库严格 Doctor 和新 Case 装配 Doctor 均为 0 error / 0 warning；正式 Project 运行成功。** 以下首轮记录对应最初示例版本；用户指出取解配额与容量的耦合后，追加修改与实际复验见文末。两轮都是指定边界的实现与行为验收，不是算法优越性或任意组件组合的证明。

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

运行记录：`examples/cases/solution_pool/.blackbase/runs/20261013T033810Z-3046aeb4cd/manifest.json`。首轮版本的小规模示例准备 8 个候选、两边各 4 个；完整 200/100/100 规模来自行为测试，不把小示例冒充该规模的运行结果。当前示例已改成独立配额与容量，见后续复验。

## 本轮边界

所有 Adapter 的正式候选提案经共同控制面登记到池；NSGA-II/III 与 SA 明确支持本轮池输入/重启组合。其他 Adapter 还需按契约接入具体输入模式。内置 Unit 继续保存数值工作投影，本轮没有把所有算法内部改成 ref-only。

池保存公开候选历史，但不自动选优、去重、复用评估或裁剪公开历史。私有草稿退出索引，物理 Snapshot 清理仍由共享存储负责；长期运行的历史/manifest 存储规模和更多后端尚未作性能验收。

标准示例验证阶段和事务；停滞指标不证明局部最优，启动 SA 也不保证获得性能提升。跨 Case 传输、CPU 并行与 L0 继续由 BlackBase 承担，MLBlack 内部运行不在本轮测试范围。

## 后续纠正：取解配额与 Unit 容量独立（2026-10-13）

用户指出 `build_solver(config={"population_size": 100})` 不应限制解池与所有算法。实际核对发现 PoolSearchSpec 曾要求 initial_count 等于 Adapter 的 population_size；NSGA-II/III 初始化又按空槽位裁剪输入，导致超额配额在种群已满后报错。这两处强耦合均已去掉。

池历史、初始取解配额、各算法成员容量和后代批次大小分别配置。NSGA-II/III 首次超额输入通过自己的环境选择选留成员，Unit 只发布一次对齐的成员更新；不足容量时按普通后代搜索扩充。通过准入却落选的候选仍是池历史的一部分，不作为未消费输入重试。脚手架、正式 Case、Catalog、AGENTS 与中文契约已同步。

纠正后的相关回归 **140 项通过，58.04 秒，5 条测试警告**；此前先执行的 31 项属于其中的子集，不重复计数。这不是重新执行首轮全部 288 项。覆盖不同容量与超额/不足配额、producer 超额准备、满种群后的部分接纳重试、异构 checkpoint、扩展成员字段/token/provenance 对齐与单次维护，以及既有 repair、回滚和复合权威。

```powershell
python -m pytest tests/test_solution_pool.py tests/test_pool_search_adapter.py tests/test_unit_scope_and_member_inputs.py tests/test_population_member_operations.py tests/test_unit_member_composition.py tests/test_proposal_repair.py tests/test_composite_population_authority.py -q --disable-warnings --maxfail=2 --junitxml=artifacts/audit/solution_pool_20261013/intake_capacity_tests.xml
```

重新执行本文的两条严格 Doctor 命令：根目录 0 error / 0 warning / 171 info，451 completed、86 skipped；新 Project 的 --build 为 0 error / 0 warning / 9 info，case-registry 与 case-build completed。根目录仍未对全部 Case 执行 --build。Catalog 双 profile 的六个键和示例 config_keys 已核验；示例不再列出全局 population_size。

独立 `run_solver.py --check` 显示 assembly ok。重新运行正式 Project，exit=0、status=ok，7 个逻辑步骤、47 次求值；默认取解 6/2 个，NSGA-II/III 容量 4/3，整个准备/搜索/恢复/返回周期成功。记录：`examples/cases/solution_pool/.blackbase/runs/20261013T043409Z-2443867d61/manifest.json`。

本次原始输出：`artifacts/audit/solution_pool_20261013/intake_capacity_tests.xml`、`intake_capacity_root_doctor.json`、`intake_capacity_case_doctor.json`、`intake_capacity_project_run.txt`。支持范围仍是已接入的 NSGA-II/III 与 SA，不能推断任意算法都能从不足数量的种子启动。

## 后续完善：闲置解回收与恢复闭包（2026-10-13）

用户确认长期淘汰且无人使用的解应适当删去，减少存储占用。本次新增 PoolRetentionPolicy：按已提交步数计时，显式消费者和 Adapter 活引用、未消费输入保护候选；部分批次压缩保留原始 row/token，过期行的值与身份索引一起退出。物理删除由共享 SnapshotStore 在提交后执行，失败保留重试队列。默认关闭，正式示例明确开启 2 步闲置与 2 次发布窗口。

历史发布只在保留窗口或显式 pin 下保证其完整值闭包可读；可传输 checkpoint 自带当前候选值。未决 Authority 提交临时固定 prepared manifest 和值，故障回滚后的 GC 不能提前删除恢复所需候选。暂存失败必须发生在登记持久提交意图前，本次修正了这一顺序。

主回归 **187 项通过，70.95 秒，无测试失败**：

```powershell
python -m pytest tests/test_solution_pool_retention.py tests/test_solution_pool.py tests/test_pool_search_adapter.py tests/test_runtime_contract_refinement.py tests/test_sa_adapter.py tests/test_checkpoint_resume_plugin.py tests/test_adapter_step_transactions.py tests/test_evaluation_evidence_recovery.py tests/test_composite_population_authority.py tests/test_project_scaffold_registration_guide.py -q --disable-warnings --maxfail=2 --junitxml=artifacts/audit/solution_pool_20261013/retention_tests.xml
```

之后补充一项快照脱离测试，并将压缩索引中的过期 token 一并移除；最后针对受影响的池、跨存储 checkpoint 与签名执行 **58 项复验通过，13.38 秒**。两批测试有重叠，不能相加为 245 项不同测试；合计覆盖 188 项不同用例，未重跑首轮全部 288 项。

```powershell
python -m pytest tests/test_solution_pool_retention.py tests/test_solution_pool.py tests/test_checkpoint_resume_plugin.py -q --disable-warnings --maxfail=2 --junitxml=artifacts/audit/solution_pool_20261013/retention_final_tests.xml
```

新增的 19 项保留策略测试覆盖两个消费者共同持有、读操作不续期、memory/file 批次压缩与真实删除、消费前缀不继续保留、发布失败回滚与孤儿清理、历史固定闭包、同名 owner 的多发布独立 lease、删除失败重试、跨存储 checkpoint、未知 Adapter 拒绝、PoolSearch 开启回收后运行/恢复、Authority 确认丢失时的池值保护和只读快照脱离。

扩展状态同时暴露旧 HMAC 的确定性问题：对加载后的语义对象再次 pickle，会因对象 memoization/别名变化得到不同字节。Checkpoint envelope.v2 改为保存一次序列化的 payload_bytes，对实际字节签名、验签后解析；不保留重复 payload。内部 v10 状态 schema 不变。既有 HMAC roundtrip 与新增字节篡改拒绝测试均通过；旧 v1 验签不通过仍拒绝。

最后重新执行本文两条严格 Doctor：根目录 0 error / 0 warning / 171 info，451 completed、86 skipped；新 Project 的 --build 为 0 error / 0 warning / 9 info，18 completed、1 skipped。根目录仍未逐个执行全部 Case 的 --build。Catalog 双 profile 核验七个键：五个主干键在两个 profile 均存在，doc/example 仅在 default；新增 tool.pool_retention_policy 的两个参数与正式 Case 三个配置项保持一致。

独立 Case --check 为 assembly ok。最终正式 Project exit=0、status=ok、Case succeeded，7 个逻辑步骤、47 次求值；L0 仍使用 threads=1/workers=1。记录：`examples/cases/solution_pool/.blackbase/runs/20261013T055520Z-7738e03c0b/manifest.json`。原始输出保存在同一 audit 目录下的 retention_root_doctor.json、retention_case_doctor.json、retention_project_run.txt 与 JUnit 文件，生成产物不提交 Git。

本轮验证没有进行长期规模性能、Redis 后端、MLBlack 内部运行或任意自定义 Adapter 历史引用追踪。它保证声明的池引用与恢复窗口下的回收行为；其他组件的证据/Artifact、算法私有历史和进程 RSS 不在池回收承诺中。源码与文档已同步更新 AGENTS、中文运行契约、Catalog、API 索引、标准脚手架工厂和正式示例。


## 子池与多角色精修（2026-10-13）

新增引用子池及 `RoleSpec/StrategySpec.pool_task=PoolTaskSpec(...)`。它们复用 SolutionPool 索引/retention 与现有 Router，不创建新的 Solver 或生命周期。任务进度和子 Adapter 分别参与同一步骤事务；输出由同一 Authority Snapshot 提交后可读。VNS 先评估任务起点，再比较邻域；所有返回候选使用自身 token 和反馈，由接收种群重新评估与选择。

本轮覆盖 **nsgablack 213 项不同测试通过，BlackBase 19 项通过**。这是相关边界验证，没有运行全仓全部测试，没有做优化性能基准。

- 池与存量组合：44 项通过，69.68 秒。其中当时的 6 项子池测试在后续复验中重复，不重复累计。
- 角色、VNS、repair、步骤事务和 checkpoint：110 项通过，77.18 秒。
- 最终子池、运行契约和脚手架：64 项通过，91.54 秒，1 条测试警告；新增独立 SA 同路径用例另有 1 项通过，1.16 秒。
- BlackBase 组件树检查和既有标准 Case 检查：19 项通过，1.08 秒。

```powershell
python -m pytest tests/test_subpool_tasks.py tests/test_pool_search_adapter.py tests/test_solution_pool.py tests/test_solution_pool_retention.py -q --disable-warnings --maxfail=2
python -m pytest tests/test_vns_adapter.py tests/test_vns_adapter_warnings.py tests/test_role_adapters.py tests/test_multi_strategy_controller_adapter.py tests/test_strategy_task_contract.py tests/test_proposal_repair.py tests/test_joint_repair_orchestration.py tests/test_adapter_step_transactions.py tests/test_checkpoint_resume_plugin.py -q --disable-warnings --maxfail=3
python -m pytest tests/test_subpool_tasks.py tests/test_runtime_contract_refinement.py tests/test_project_scaffold_registration_guide.py -q --disable-warnings --maxfail=2 --junitxml=artifacts/audit/solution_pool_20261013/subpool_final_tests.xml
python -m pytest tests/test_subpool_tasks.py -k same_task_binding -q --disable-warnings --maxfail=1
# 在 blackbase 仓库：
python -m pytest tests/test_project_adapter_components.py tests/test_project_check_output.py -q
```

10 项新行为测试包含：20 个同值不同 token 起点、两类四实例 VNS、120 条结果分批返回 GA 竞争；第二个 worker 更新失败的整组回滚；零接纳重试原始输入；子池共享/解除/可传输恢复；输出提交可见性；正式 CheckpointResumePlugin 恢复进行中的任务；不支持输入契约的 Adapter 拒绝；嵌套同名角色命名空间隔离；包装后仍拒绝共享可变子实例；相同任务入口运行 SA。

Catalog 的 adapter.pool_task/tool.pool_task_spec 在 default 与 framework-core 均可发现；example.pool_refinement 仅在 default。没有同步数据库。AGENTS、正式运行契约、编排讨论、中文解池文档、两个 API 索引和可选模板提示均已同步。

严格 Doctor 的根目录检查包含 framework-core Catalog；根目录不执行所有 Case 的 --build。实际 Project 的 --build 已对 pool_search/pool_refinement 两个 builder 执行，0 error / 0 warning / 14 info，24 completed、2 skipped：新 Case 没有本地 catalog TOML，Project 命令未重复执行 Catalog 审计。全局 Catalog 已在根目录单独执行，不能把这两个 skip 隐去。

最终根目录结果：0 error / 0 warning / 173 info，457 completed、88 skipped（61 个 case-build、26 个 case-registry、1 个 framework-registry）。生成输出保存在 `artifacts/audit/solution_pool_20261013/subpool_root_final.json` / `subpool_case_final.json` / `subpool_project_final.txt`；JUnit 见同目录 subpool_final_tests.xml。生成产物不提交 Git。

标准 Project 最终运行记录：`examples/cases/solution_pool/.blackbase/runs/20261013T065727Z-0f18ed6a5b/manifest.json`，status=ok，exit_code=0。pool_search 为 7 步/47 次求值；pool_refinement 为 25 步/280 次求值，两个 Case 均 succeeded。实际授权为每 Case threads=1/workers=1；四个 VNS 是逻辑实例，不是四线程性能结果。独立 --check 和 Project runtime_state 都显示真实 NSGA-II、四个 VNS、PoolTaskAdapter 与 ContextGaussianMutation。

为显示上述组件，本轮只在 BlackBase 的通用 Case 检查/运行摘要中增加 adapter_components，通过声明的 step_transaction_children 遍历，不扫描私有对象图或导入优化算法。重复/循环实例拒绝。BlackBase 原有未提交改动保持原状，本轮显示功能单独提交。

独立提交点：nsgablack 运行机制与契约为 `fd49cc47`；BlackBase 组件展示为 `611d385`；示例、Catalog 与本验收记录随后单独提交。没有推送远端。

输出集合包含准入的起点及试探解，不承诺每条都是局部改进。输出子池不再使用后需显式 drop，才解除该集合的回收保护。SA/VNS 已验证此任务入口，NSGA-II/III 声明 initialize/compete；MOEA/D 子问题比较与目标槽位绑定尚未接入，不宣称任意 Adapter 已自动支持。跨 Case 并行和 L0 仍属 BlackBase，本轮没有改 MLBlack。
