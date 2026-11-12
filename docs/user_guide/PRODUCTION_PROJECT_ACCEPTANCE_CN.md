# 原生产排程 Project：完整使用链验收

验收日期：2026-11-02。运行证据保存在仓库根 `results/acceptance/production_20261102/`；
排程与对照报告保存在 `examples/cases/production_scheduling/results/quality/acceptance_20261102_final/`。

后续大预算揭示了小规模检查未覆盖的管线 RNG 恢复缺口，已补显式 codec 与回滚。
预算显示和简易 checkpoint 入口也已继续完善，最新用法与复核见
[checkpoint 与大预算运行](PRODUCTION_CHECKPOINT_AND_LARGE_RUN_CN.md)。下文保留首次验收的历史范围。

## 验收范围与结论口径

本轮检验原数据、正式装配、Project/L0 运行、方向子池精修与返回、整数导出、
原始目标复核、取消、预算、checkpoint 和供应嵌套交付。
它是有界工程验收，不是充分收敛、文献水平、多种子质量或双层 200×100 的证明。
本轮仅在本机执行；没有操作桌面、调用付费 AI、启动远端 Worker 或部署网页。

两个原有模型分别验收，不相互替代：

- 独立生产质量组：22 机种、31 天、四个原始目标，默认单机种日产上限 10000。
- 供应嵌套：638 个逐笔提前量变量，生产内层保留五目标、日产上限 3000。
  Day 0 库存固定，未来事件最早到 Day 1；逐物料总量守恒。

## 用户从哪里开始

以下命令均在 `C:/Users/hp/Desktop/nsgablack` 执行。

1. 检查标准 Project 的真实装配：

   ```powershell
   python examples/cases/production_scheduling/run_project.py --check --build-check
   ```

   该默认组只是 4 机种、10 物料槽位、1 代的接线检查。
   不应根据它的成功推断完整模型已经验收。

2. 跑原始数据的先导与 Greedy 对照：

   ```powershell
   python examples/cases/production_scheduling/run_quality_benchmark.py --groups pilot greedy --seeds 42 --run-id my_production_acceptance
   ```

   每次使用新的 run-id，避免混入旧运行产物。质量 runner 调用原 `run_project.py`，
   不拥有第二套算法循环；正式 manifest 在 Project 的 `.blackbase/runs/`。

3. 查看 `results/quality/<run-id>/comparison.csv` 与 `recommendations/`。
   `production`、`stability`、`balanced` 是明确的显示选择政策，不能混成唯一最优解。
   先确认 CSV 的硬可行性、库存、原始目标，再讨论产量和稳定性的取舍。

4. 修改对应位置，再运行一个新 run：

   - 问题与约束：Case 的 `problem/`。
   - 领域初始化和变化：`pipeline/neighborhood_search.py`。
   - 探索、方向精修、返回竞争：`adapter/directional.py`。
   - 资源、预算、种子与运行组：Project 的 `project_config.py`。
   - 最终整数导出与失败否决：`plugins/runtime_plugins.py`。

需要供应调整时运行已有独立 Project：

```powershell
python examples/cases/supply_adjustment_nested/run_project.py --group baseline --run-id my_supply_baseline
```

它检查零调整通过真实生产子 Case 求值的交付链；不是已经搜索了供应方案。
外层搜索使用 `pilot` 等显式组，预算明显大于单个 baseline。
配置了 `BLACKBASE_JOINT_REDIS_URL` 的部署会选择远端模式；本轮明确使用本地模式。

## 本轮发现并修正的实际问题

### 1. 156 个物料 ID 被误当成 156 个连续槽位

原表有 156 个实际物料 ID，但最大 ID 是 157。旧质量组使用 156 个槽位，
加载器会跳过 ID 157 的 BOM 关系与供应，不能称完整数据。
本轮把正式默认、质量组和报告复核统一为 157 个槽位，并增加真实数据测试，
确认最后一个槽位确实保留 BOM 与非零供应。
原 BOM/SUPPLY 字节未修改。

修正前的 `acceptance_20261102_localtmp` 只作为问题复现保留，
不能与修正后的最终组混合比较，也不能拿旧模型分数证明新模型改善。

### 2. 嵌套导入依赖调用者之前加载过什么

生产组件先被加载时，其目录可能已在 `sys.path` 中。
BlackBase 原导入作用域遇到已有目录就跳过，导致内层构建读取外层的短名 `adapter`，
最终错误提示却像缺失 `build_solver`。
本轮在共享底座修正路径优先级，并在退出/异常时恢复完整原路径。
底座回归覆盖预先存在的目录、重复路径、嵌套与异常恢复；生产和供应组合回归验证实际调用链。

### 3. 数据失败会静默变成随机问题

正式 Problem builder 之前使用 `fallback=True`。
本轮改为显式报错；增加缺失 BOM 测试，禁止在用户指定数据失败后悄悄生成随机数据。
底层数据工具的显式 fallback 能力仍存在，正式 Case 不默认启用。

### 4. 使用说明仍有失效路径与不支持的后端

Case README 原命令少了一层 `cases/production_scheduling/`，还展示 process 评估。
已改为实际验证的 Project 质量入口，并明确正式评估链使用 thread。

## 实际完整数据运行

最终质量 run 为 `acceptance_20261102_final`，种子 42，单线程授权、无 GPU。

- 方向精修先导：17 个提交步骤、136 次算法求值；端到端约 17.80 秒，Case 内约 14.44 秒。
  完整走完 MOEA/D → 方向子池 VNS → 原 MOEA/D 返回竞争。
  报告中的产量推荐为 76211，稳定推荐为 46824，折中推荐为 73236。
- Greedy：1 步、1 次算法求值；端到端约 5.53 秒，产量 66551。
- 两组共输出 20 份 CSV 复核记录，原始目标与独立累计库存检查写入 `comparison.json`。

二者求值预算不同，不能据此声称方向精修在等预算下优于 Greedy。
端到端时间包含启动、加载、搜索、导出与收据处理，不是纯框架开销测量。
软性活跃机种不足等偏离单独报告；硬可行不代表满足全部软偏好。

供应 baseline 为 `acceptance_20261102_baseline`：

- 正式父 Case 约 15.06 秒，子 Case 真实执行 7 个逻辑步骤、38 次算法求值与 1 次独立审计。
- 外层原始目标为 `[-69672.7168, 0, 0]`；638 个提前量均为零。
- Day 0 与物料总量差为零，交付 22×31 排程。
- 子预算已结算，38 次实际求值记入父预算，154 次未用额度返还，没有未决预留。
- `joint_summary` 与生产子 summary 均以发布收据实读验证。

该嵌套结果保留原浮点排程交付，不冒充独立生产组的整数 CSV，也不与其四目标指标直接比较。

## 取消、预算与恢复怎样验

新增 `tests/test_production_project_acceptance.py` 使用原 BOM/SUPPLY 和 canonical builder：

- 在方向精修途中保存并恢复 checkpoint，核对冻结历史引用、最终数值轨迹、成员引用对应内容和 raw feedback。
  后续新提案是新发布，不要求两次独立延续的随机 record_id 相同。
- 实际 update 后注入取消，要求 Unit、任务、Pool 和 Authority 回滚；发生的两次求值仍计费，随后可完成计划。
- 第三次真实 Problem 求值时触发 CancellationToken，剩余批次停止，不产生提交代，已发生的三次求值保留且预留清零。
- 本地评估上限设为 5，要求只计 5 次求值、2 个提交步骤；未完成的计划不能被标成已完成。
- 输入 BOM 缺失时明确失败。

这证明运行层能力已接通，不代表工作区已经提供方便的取消/恢复按钮。
Project `--resume-from` 是阶段级恢复；不能把跳过成功 Case 与 Solver 内部 checkpoint 续算混为一谈。

恢复测试实际生成签名 checkpoint 文件，通过公开 `save_checkpoint/resume` 及正常 run 恢复门闸，
在普通初始化钩子核对恢复前缀后继续运行。测试密钥仅在测试进程临时使用，不作为运行凭据保存。

相关验收最终为 nsgablack 95 项、BlackBase 18 项通过。
`complete.xml` 保留一次把“已排队恢复”误当成“已应用恢复”的测试失败；
修正测试调用顺序后，`disk_restore.xml` 的 5 项定向重跑全部通过，未修改恢复时序。
这是去重后的覆盖数，不把重复执行累计成更多测试。
生产 Project 的严格 Doctor/build 检查为 0 error、0 warning、10 info；
该次未启用 Catalog 审计，coverage 的跳过项保留在 `doctor_final.json`，不算 Catalog 已验收。

## 环境失败与仍待完善的使用体验

首次执行遇到沙箱临时目录权限错误：测试 fixture 与 Artifact staging 都无法创建临时目录。
失败记录保留在 `focused.xml` 和质量 run `acceptance_20261102`。
后续仅给本轮子进程指定仓库内 TEMP/TMP，并使用独立 pytest basetemp；没有更改系统全局设置。

仍需改善：

- 默认 smoke 与真实数据组应在工作区明显区分，避免用户误把 smoke 当求解结果。
- 预算耗尽当前结果可能显示 `termination_reason=user_stop`；计数正确，原因展示仍不够精确。
- Case CLI 没有直观的内部 checkpoint 续算入口；现有 Plugin 能力不等于产品已经好用。
- 本轮没有验收浏览器编辑器、组件小窗、按钮、远端分发或双层大规模收敛；这些不能写成已完成。

最终机器可读汇总见 `results/acceptance/production_20261102/summary.json`；
JUnit、Doctor coverage、正式 manifest 和失败尝试分别保存，不用最终成功覆盖失败历史。
