# 有界生产运行成本诊断

这是标准 Project，复用原 `supply_adjustment_nested` 和 `production_inner` 两个 Case 的规范工厂。
本目录不复制模型、数据、算子、结果发布或调度循环。两个同名 Case 仅通过
`load_case_builder` / `build_case` 转发装配；内层请求仍由正式 CaseRuntime 在本 Project 下解析。

固定输入为原 `production_scheduling` 的 `machine_material_mapping.csv` 和 `SUPPLY.xlsx`：
22 台机器、157 个材料槽位、Day0..30 共 31 天。外层使用 evaluation-only 的零移位供应候选，
仅求值一次；内层原五目标、每机上限 3000、今天库存固定，MOEA/D 容量 16、逻辑步上限 2、raw 额度 32。
小额度不保证满两步或填满全部成员，实际提交数和求值数以正式结果为准。短探针不会进入 VNS 阶段。

不传 `--parallel`，原评估在 Case 主线程执行，便于外置函数耗时 profile。
可信环境存在 `NSGABLACK_RUNTIME_PROFILE_DIR` 时，两个薄工厂在原 canonical 装配返回后调用
已注册的 `sitecustomize.start_profile()`；缺少可调用 hook 时明确失败。普通 baseline 不调用该 hook。
因此 cProfile 聚焦装配后的运行与 finalization，导入/装配使用外置 wall/CPU 元数据单独计量，
不能把此 profile 称为整个进程启动的函数计量。Profile 文件保存由外置 sitecustomize 负责。
可选 profiler/decision trace 与原内层日志/CSV/Excel 导出均关闭；正式 SolverResult、
`production_summary`、`joint_summary`、`candidate_search_audit`、证据归档及其 seal/收据仍保留。
本地输入使用原 v1 task 的显式路径与 SHA；不声称测试了跨机 portable Artifact 输入。

Project 使用本目录独立 SQLite lease/control/budget 和 Filesystem Artifact authority。
可信环境 `NSGABLACK_RUNTIME_COST_RUN_ID` 接受单个文件名标识；`NSGABLACK_RUNTIME_COST_RUN_ROOT`
必须是本 Project 的 `.blackbase/runs/<RUN_ID>` 绝对目录，lease/control/artifacts 与正式 manifest
都进入该目录。此限制来自共享 Filesystem authority 的 Project 范围和 Recorder 的固定目录，
不接受任意外部输出路径。未传环境时使用 `manual`，重复正式运行须使用新标识。
L0 授权 1 thread、无 GPU，父内存 1536 MiB、内层 768 MiB；这是资源授权，**不是 OS CPU/内存硬限制**。
普通运行的父 Case deadline 45 秒，终止宽限 2 秒、kill 宽限 1 秒；内层 deadline 35 秒并继承父级取消。
外置 runner 负责进程树内存监督、普通命令 60 秒总界和 cProfile，不由本 Project 另造监督器。
2026-11-02 起，bootstrap 的 profile 模式允许父 80 秒、内层 70 秒、整个命令 100 秒，以覆盖计量扰动和冷启动；
搜索规模、逻辑步数、评估额度、模型与内存停止阈值均不扩大。报告必须区分普通耗时和计量耗时。
SnapshotStore 保留原 Case 默认设置，不能把这次本地小探针当作旧 File 后端长算的等价复现。

仅装配检查（不运行模型）：

```powershell
python examples/cases/runtime_cost_probe/run_project.py --check --build-check
```

正式运行入口：`run_project.py::main(argv=None)`；程序调用使用
`nsgablack.project.project_runner.execute_project(project_root, group="default", run_id=...)`。
运行前须由调用方按本次诊断约束启用外置监督。

## 监督运行与读结果

已安装开发框架与 `psutil` 时，在仓库根目录执行：

```powershell
python examples/cases/runtime_cost_probe/run_probe.py --mode baseline --run-id my-baseline-01
python examples/cases/runtime_cost_probe/run_probe.py --mode profile --run-id my-profile-01
python examples/cases/runtime_cost_probe/profiling/report.py --run-root <完整的my-profile-01运行目录>
```

2026-11-02 新增 `--workload iteration`：沿用原多阶段排程装配，内层运行 8 个逻辑步、
评估额度 96，Project 额度 97；旧 `bootstrap` 档仍是两步、32/33 额度。
两个档位均不扩大池容量、机器数、天数或修改目标/修复规则。示例：

```powershell
python examples/cases/runtime_cost_probe/run_probe.py --mode profile --workload iteration --run-id my-iteration-01
```

迭代档装配只读 StepCostObserver，使用正式 attempt hooks 记录逐步 wall/thread CPU、
求值数及可选 profiler 自耗时计数差，写入 `steps-<生产PID>.json`。
观察器不请求求值、不维护预算、不写共享 context、不修改算法状态；profile 计数采集本身有成本。
实际进入正常搜索须查看 MOEA/D `_variation` / VNS `change` 调用，不能只按步号或总评估数推断。
本轮验收见仓库 `results/test_runs/steady_iteration_20261102/verification.json`。

Unit 步骤快照的对照可使用 `--mode profile --workload iteration --unit-mode legacy`。
这个选项只在独立诊断进程里，把 Binding 的步骤接口绑定回原持久 codec，并恢复成员通知的旧摘要路径；
它不是生产开关，也不读取旧工作树。默认 `native` 使用当前实现。两种方式的模型、算法、种子和预算一致。
两次 80 秒的 profile 截止失败后，迭代档的等待上限调整为父 180／内层 160／监督器 200 秒；
普通迭代档为父 90／内层 80／监督器 110 秒。bootstrap 档仍用原来的等待上限。
这些调整只容纳诊断扰动，不增加任何搜索步或评估额度。实际生效上限见 supervision.json。

主要耗时定位还提供低扰动的 `--mode timing`，不启用 cProfile。
它通过嵌套作用域记录 Snapshot 写入、repair、原始 Problem/约束、回滚捕获和池准备的 wall/thread CPU；
还分别记录提案/更新、预算 status/reserve/consume/complete、取消检查、context、Event、
Authority 发布和最终证据归档。`step_body_other` 是扣除已测子作用域后的剩余工作，
不是完整 step，也不能把没有直接测量的部分统称为审计。
子作用域从父作用域中扣除，所以 `wall_exclusive` 可以在同一线程内比较，`wall_inclusive` 不可相加。
GC 时间另外记录，已包含在上述作用域中，不能再加一次。Windows thread CPU 时钟分辨率较粗，
短小的 raw Problem 调用主要看 wall 时钟。逐步统计仍写入 steps-<PID>.json。

`--memory-mode legacy` 在诊断进程里保留原 Memory Snapshot 传输往返；默认 native 使用闭合数据冻结。
`--repair-mode legacy` 只恢复选择期的重复库存读取；默认 native 在库存不变的选择作用域内复用结果。
两个参考开关仅用于 profile/timing 对照，不属于生产装配配置；问题、算法、随机种子和评估额度不变。

`--io-mode legacy` 在装配后关闭本次预算连接作用域，恢复短连接操作，并让 Memory 的
内容导出走完整编码；仅用于 timing/profile 参考。默认 native 保留运行时复用与有界字节缓存。
新的计时还拆出 budget_connect/sql/commit/context_exit/close，以及 Snapshot 的 capture、
validate、freeze、safe_wire、transport_json 和 canonical_json。递归校验／wire 构造只给
外层入口计时，仍有一次轻量递归检查的测量扰动；不能与旧粒度的探针直接算提速。
透明计时包装显式对齐 Memory 的函数身份防护并断言准备分支未变，不强制打开原本关闭的路径。
连接可能在装配期已经打开，计量期 connect=0 不代表整条 Case 无数据库连接。

`--timing-detail coarse` 不包装递归的 validator／safe-wire 节点入口，仍计量完整
Snapshot 写入及其他外层作用域，适合比较遍历次数不同的实现。fine 与 coarse 不直接算提速。
`--hotpath-mode legacy` 在诊断进程恢复合并遍历前的 Memory 准备函数，保留当前预算连接、
canonical 字节缓存和问题修复；只允许 profile/timing，不是生产配置。
本轮曾试验提前确定 repair 的开机选择阈值，未得到稳定收益后已撤回，当前保留原 repair。
具体运行记录及波动限制见 `results/test_runs/native_tree_repair_20261102/FINDINGS_CN.md`。

本轮正常迭代定位和完整输出对账见
`results/test_runs/main_iteration_cost_20261102/FINDINGS_CN.md`。选择期库存复用只在
同一天、尚未分配产量且库存不变的循环内有效；不能跨分配、日期、调用或供应方案复用。

每次必须使用新 run-id，不覆盖旧证据。监督器启动隐藏子进程，仅记录并处理本次进程树及其创建身份。
启动前可用内存须不少于 512 MiB；运行中采样家族 RSS 超过 512 MiB、系统可用内存低于
128 MiB 或总时间超过所选档位的上限时停止自己的进程：bootstrap 为普通 60 秒／profile 100 秒，
iteration 为普通 110 秒／profile 200 秒。采样阈值仍不是 OS 硬限制。

`supervision.json` 记录状态、实际时间、采样内存和进程身份；`result.json` 是正式 Project 结果。
成功后通过 ArtifactPublisher 核验 joint_summary 和其绑定的 production_summary，另存
`verified_production_summary.json`。不能用一个未核验的 CSV 或 stdout 替代正式交付。
失败或中断的 manifest 与预算证据原样保留；缺少最终统计不能解释成消耗为零。

profile 使用 cProfile 默认 elapsed 时钟，不是 CPU 时钟。`profiles/process-<PID>.json`
独立记录装配前后 wall/CPU 时间；`.prof` 仅覆盖该 Case 装配后的主线程。
`profile_analysis.json` 按不重叠 self elapsed 分组，inclusive 调用边界不能相加，
父进程等待与子进程工作也不能相加。profile 自身有成本，可能触及 Case deadline；
只有驱动或父级 profile、没有完整生产子进程和成功正式结果时，不算生产成本验收通过。

## 2026-10-30 本地验收边界

成功探针实际提交两步、算法求值 18 次、最终审计 1 次。这两步是初始化与补齐，
尚未验证 MOEA/D 稳态变化、VNS 或长期增长索引成本。五目标、所有原始硬约束与 Day0
分别核对，修复前后完整最终排程一致。无 profile 的修复前一次运行 23.43 秒，
修复后两次 22.17／22.93 秒；样本不足以得出稳定提速比例或预测两层 200×100 耗时。

完整的函数计量确认默认空 context 插件与 retention 重复复制已消除，但 profile 总耗时
受持久 IO 与计量扰动影响，并未稳定下降。失败尝试均保留，详见仓库
`results/test_runs/runtime_cost_followup_20261030/verification.json`。
