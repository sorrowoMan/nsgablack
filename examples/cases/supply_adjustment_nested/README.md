# 供应调整与生产排程联合求解

外层 NSGA-II 搜索供应事件提前天数；每个修复后的候选，通过正式 `production_inner` 子 Case，在该候选的供应表上运行原生产排程算法。子 Case 返回真实排程并封存 Artifact，外层按候选身份关联产量、干预次数和提前天数。

## 运行

在已安装本框架栈的仓库根目录：

```powershell
python examples/cases/supply_adjustment_nested/run_project.py --check --build-check
python examples/cases/supply_adjustment_nested/run_project.py --group baseline
python examples/cases/supply_adjustment_nested/run_project.py --group pilot
python examples/cases/supply_adjustment_nested/run_project.py --group joint_acceptance
```

需要让内层 Worker 不依赖协调端数据路径时，使用显式 `--group portable`：
`production_sources` 先发布 BOM／到料原始字节，再向外层及子 Case 传递正式 ArtifactBinding。
外层仍在协调端从同一 SHA 的原文件构建问题；Worker 从 Artifact 读取，代码按预部署清单核对。
该组不会自动开通 Redis／HTTP 服务或上传代码，也不会改变原始预算；跨机放置另由 L0.nested_execution 配置。
详见 [内层 v2 输入](cases/production_inner/README.md)。

`baseline` / `default` 对零供应调整做一次真实内层求解；`pilot` 接着评估最多 8 个外层供应候选。`joint_acceptance` 进一步用种子 42、43、44，分别以相同较高预算重新求解零调整和搜索选出的供应方案。每项复核从 `search` 阶段已封存的 `joint_summary` Artifact 读取供应候选，重新运行内层，不能沿用搜索时的低预算产量。

这些命令使用完整原数据，有实际计算成本。Project 共享预算上限现为 20000 次 `evaluations` 和 100 次独立 `audit_evaluations`；前者包含外层评分行和内层生产候选，不应把子预算结算再重复相加。单个子 Case 搜索预算为 192，复核预算为 512；步数分别为 7 和 24，属于有界试验，不代表充分收敛。

## 本轮保持的模型

- 22 个机种，31 天（Day 0..30）。原材料 ID 最大为 157，虽然只有 156 个实际 ID，仍需 157 个槽位，避免漏掉材料 157。
- 原 BOM 与 SUPPLY 文件不改写；逐物料总供应量守恒。Day 0 是今天，库存不能移入或移出，未来事件最早到 Day 1。
- 外层维度保留原有 638 个未来供应事件；其中 7 个 Day 1 变量为 `[0, 0]`。
- 内层保留 phased MOEA/D + VNS、5 个原始目标、单机种日产上限 3000、原约束与偏好。7 步搜索配方前 5 步探索，第 6 步是 VNS 起点评估，第 7 步才产生 VNS 邻域变化；24 步复核则先探索 8 步，再进入 VNS。
- 外层原始目标是 `[-真实排程总产量, 移动事件数, 总提前天数]`。供应总量不能代替生产产量；正式内层失败会传播，不能替换成代理分数。

## 装配与交付

`project_config.py` 管理阶段、L0 授权、总预算与正式 Artifact 输入。父 Case 的 `build_solver.py` 仍是唯一装配入口；算法循环由原 Solver 持有。`production_inner` 用生产 Project 的 canonical builder 接收显式场景，旧随机算子在正式子进程中运行，不污染外层随机流。

`joint_summary` 保存精确 SolutionRef、候选 token、调整后供应、对应排程、原始目标、内层预算结算、文件 SHA256、子 Case 身份和发布收据。最终供应方案不能靠相同数值或行号猜对应排程。

本地默认使用 SQLite 权威；可信部署注入 `BLACKBASE_JOINT_REDIS_URL` 和 `BLACKBASE_JOINT_NAMESPACE` 后，阶段经正式 ExternalCaseWorker 运行。云端 Artifact 仍由中央原权威封存，HTTP 仅传输字节，见 [BlackBase Artifact 通道](../../../../blackbase/ARTIFACT_HTTP_CN.md)。不要在任务中传认证 URL 或令牌。

## Cases

- `cases/supply_adjustment_nested/`：供应候选、问题修复、正式内层调用和联合结果交付。
- `cases/production_inner/`：必须由父 Case 提供版本化 `task`，独立无 task 的 build 应明确失败；其有效装配和运行由正式子调用测试验证。

旧 blacklist / callback / Redis candidate-worker 入口未纳入本次正式路径验收，不应按旧 README 的配置冒称已验证。本轮不使用 mlblack，也没有改变其它生产 Project 的业务模型。


## 逐笔到料的多天搜索（2026-10-29）

每个变量仍是某个物料、某一天的一整笔到料的提前天数。不同批次独立选择，不是整张供应表一起提前。第 d 天到料的合法提前量为 `0..d-1`，最早到第 1 天，今天的逐物料库存保持不动。移动量不拆分、逐物料总量不变；最多移动 100 笔。

旧搜索的问题是：密集整数初始化／高斯变化先生成很多非零值，超限裁剪再优先保留短提前，最终候选集中在 1～2 天。新候选管线使用：

- 稀疏初始化：先均匀抽取 0～100 的移动笔数，再不放回抽取可移动批次，每笔独立抽取自己的合法天数。
- 明确变化：新增一笔、撤销一笔、交换活动批次、改动一笔的日期；改期一半走整数邻域，一半在完整合法日期域重抽。种子可重放，输入不原位改写。
- 确定性超限修复：已合法且不超限的向量不变；交叉等产生超过 100 笔时，按候选规范值与事件身份的 SHA256 排序保留，不按提前天数或到料量排序。该策略稳定、幂等，无运行中随机状态。

这是消除隐藏的短提前裁剪偏好，并非对整个可行域均匀采样的数学声明；不同事件的可提前上界本来就不同。新方案仍由原始三目标比较，不能把“必须多天”作为胜出条件。

`pipeline/main.py` 的 `local_step_days` 表示改期的整数邻域半径。旧 `mutation_sigma` 只保留显式整数天别名；不能继续传入高斯标准差 `0.5`，也不能和新参数同时指定。

```powershell
python examples/cases/supply_adjustment_nested/run_project.py --group event_comparison
```

此组先将已封存旧方案的决策向量导入新权威，再搜索最多 **72 个外层候选**（种群 12、5 次变化代），搜索每候选采用种子 42、7 步、192 次内层评价上限。随后将零调整、旧方案、新方案分别以种子 42/43/44、24 步、512 次内层评价上限重算，共 9 项复核。所有复核使用同一模型、同一配方和预算上限，实际求值次数会因算法路径而不同；不宣称严格等调用次数。

`prior_plan_binding.json` 是部署侧可信旧产物绑定，里面没有账号或认证信息。`supply_plan_import` 只读原 Artifact ledger/store 验证旧收据，核对当前原始输入 SHA 后在当前权威发布 `candidate_plan`；旧生产分数不被沿用。新产生的评价获得新 token，保留 `derived_from` 追溯。只在可访问原文件权威的部署中运行此比较组；普通 `baseline/pilot` 不读取旧产物内容，也不要求旧绑定 JSON 存在。缺少绑定时，比较组的导入步骤会明确拒绝执行。

除最终 `joint_summary` 外，`candidate_search_audit` 封存本次全部接纳候选、各自的真实生产子结果收据和稀疏调整内容。相同数值但不同 token 仍分别记账；分析去重摘要不能替代解身份。


## 封存成功、回传失败后的续验

本次云端 72 候选搜索的生产子结果和父级 `joint_summary/candidate_search_audit` 已封存，但私有 Redis 的 32MiB `maxmemory` 不足以接收完整结果，原 B1 Project 因传输失败而结束。不能把原失败记录改成成功，也不能直接用 `--resume` 假定已有父 Case 成功结果；该路径会重发失败的搜索。

现有正式 `supply_plan_import` 可从 B1 原发布收据只读导入已选中的向量。可信部署的 `recovered_plan_binding.json` 固定该绑定后，可以用新 run 执行：

```powershell
python examples/cases/supply_adjustment_nested/run_project.py --group event_recovery_comparison
```

此组仅执行旧方案导入、封存新方案导入和三方案 × 三种子的 9 项复核，不重复 72 次搜索。B1 搜索与 B2 复核保持各自真实身份和预算 scope；组合报告是分析产物，不是虚构的单次成功运行。B1/A1 源 Artifact 目录在导入进程内只读挂载，结束后核对原文件 SHA、大小和修改时间。

Broker 的容量要按实际结果体积设置，不能只估计任务请求大小。本次私有 Redis 最终采用 512MiB `maxmemory`、1GiB 容器硬界、`noeviction`；这是本次部署配置，不是此模型的数学参数。后续更大结果适合继续收敛为引用交付。

本轮实际得到 72 个不同向量。新方案移动 19 笔、累计提前 66 天，最长 11 天；三种子平均产量 72136.842667，旧方案为 72174.797333，零调整为 70853.16。它以平均产量接近旧方案换取更少干预，不应称所有目标全面优于旧方案。完整九次结果、浮点排程、跨轮核对和原始证据见 [本轮报告](../../../results/test_runs/supply_event_search_20261029/README_CN.md)。


## 三机容量探针与双层放大

容量探针通过可信部署设置 `NSGABLACK_SUPPLY_CAPACITY_PROFILE_JSON`，或以 `NSGABLACK_SUPPLY_CAPACITY_PROFILE` 指向 JSON 文件；两者互斥。不提供配置时，原有组与资源声明不变。示例配置：

```json
{"schema":"supply_adjustment_nested.capacity_profile/v1","node":"local","inner_threads":8,"parent_memory_mb":1536,"inner_memory_mb":1024}
```

部署还需显式提供 `BLACKBASE_JOINT_NAMESPACE`；云端队列认证与 Artifact 通道由可信部署提供。使用标准入口 `python run_project.py --group capacity_probe`。三节点共同的 L0 总额为 11 threads、3 workers、6656MiB，分别来自 local 8/1536、risk 2/2048、data 1/3072；每个实际 Case 只获本节点的请求，操作系统还有限额。总额代表集群，不代表协调机的物理核数。每次运行的预算 scope 独立。

探针支持 local 1/4/8、risk 1/2、data 1，各节点完成一档后才进入下一档。实际是否执行中间档取决于已测瓶颈；若原始评分只占很小部分，不用整轮重复运行来猜测不足一秒的线程收益。每档都是完整标准 Project/Case 调用；这些既有探针记录的节点间并行粒度仍是独立 Project。

2026-10-30新增完整子Case批次入口：`--outer-parallel-workers 2` 请求同批运行两个生产Case，和内层原始评分线程数分别配置。
不再仅为此参数拒绝装配。Project显式配置 `L0.nested_execution.case_names=["production_inner"]` 后使用共享标准外部Worker；
未配置时仍在父本机授权内执行。远端资源由各target共享持久L0账本授予，不用协调机线程数裁剪远端需求。
`--outer-parallel-backend redis`仍拒绝，外部队列须在Project配置，不能绕到旧私有candidate协议。
装配与验收见[内层批次执行](../../../docs/architecture/STATE_COST_AND_NESTED_EXECUTION_CN.md)。
实际三机上线前还须保证Task中的BOM/到料源和冻结生产代码路径在目标可读，或经正式Artifact/Provider交付；
当前本地绝对路径不能因开启队列就自动变成远端路径。既有三机和长算例结果不因此升级为新分发验收。

探针两层均设置 population=200、generations=100，但显式将外层限制为 2 次、每个生产子 Case 限制为 512 次评价。每档上限是 1026 evaluations 和 2 audits；这用于测吞吐、工作集和开销，不表示已完成 100 代。正式总预算要在测量后确定；MOEA/D、VNS 和阶段切换的提案数量也不能恒按 population×generation 计算。

共享通道的默认时间上限为每个内层 Case 600 秒、整个探针阶段 1500 秒。它们是超时保护，求值上限仍是 1026/2。此前 300/600 秒试验在数据机成功，而本机与风险机在内层已消耗并结算 512 次后仍未完成审计；本机独立 SQLite/FS 对照的两个子 Case 分别约 170/142 秒。因此网络试验单独放宽时间政策，保留原失败记录；不会因此延长资源 lease TTL、绕过 fence 或宣称原 300 秒验收通过。结果与原始证据见 `results/test_runs/supply_capacity_20261029/`（仓库根目录）。

内层线程现在经 Solver 中央统一计数、预算、偏好、hooks 与原始反馈。原始线程 worker 不持有 Solver/Bias，保留每行上下文与 Feedback.info，异常不静默降级。当前 `with_parallel_evaluation` 的正式 Problem 路径明确支持 thread；process/ray/joblib/auto 未通过该正式边界验证而拒绝，旧数组入口不因此宣称得到验证。repair、变化和中央决策仍可能串行，线程数不等于实际 CPU 核数。

生产 summary 的 `parallel_last_dispatch` 是最后一次原始批次；VNS 单点可能合法走 inline。`parallel_raw_dispatch` 累计记录整轮实际线程批次、完成行数、PID/线程数量与原始批次 CPU/墙钟时间。完整进程树 CPU、内存、网络、IO 和端到端耗时由部署采样记录，不能用最后一批或仅 n_workers 配置冒充整轮吞吐。

完整内层验收需核对实际 100 次逻辑提交、Router 游标、33 次 explore／67 次 exploit、终止原因，以及正式 Case 结果和预算结算；仅配置 generations=100 或耗尽评价预算都不足以证明完成。固定一个外层向量做此验收，也不代表外层 GA 已运行 100 代。

默认内存 SnapshotStore 在运行期保留历史快照与证据引用；default TTL 为 None 时不能假定它会自动释放。更大内层可在候选操作之前通过现有 `set_snapshot_store_backend("file", ...)` 配置受控目录，并核对实际 FileSnapshotStore 及配套 SQLite Journal／Authority。各 Case 需隔离目录，不能静默退回内存后端。文件后端保留原证据语义，同时增加文件 IO、编码和暂存成本，仍需量测工作集与磁盘上限。

磁盘限速会让任务自身等待；全机 iowait／PSI 不能单独证明业务磁盘过载。部署保护应同时记录物理设备活动、任务 cgroup 的 IO／pressure 和实际生效的硬限，并保留采样窗口。未采集的历史指标应记为未知，不能用运行后的空闲基线反推旧运行状态。
