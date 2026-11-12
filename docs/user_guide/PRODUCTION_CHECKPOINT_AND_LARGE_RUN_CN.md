# 排程 Case：预算原因、checkpoint 与大预算运行

更新日期：2026-11-02。本文对应现有 `production_scheduling` Project，
不另建求解循环；原始数据仍为 22 机种、157 个物料槽位、31 天。

## 最简单的正式 Project 用法

在仓库根目录运行一个完整方向精修组：

```powershell
python examples/cases/production_scheduling/run_quality_benchmark.py --groups directional --seeds 42 --run-id my_full_run
```

该组自动开启签名 checkpoint，每 10 个已提交步骤保存一次，正常完成后再保存最终检查点。
输出目录为：

```text
examples/cases/production_scheduling/results/quality/my_full_run/
  benchmark.json
  comparison.json
  comparison.csv
  recommendations/
  quality_directional_s42/
    project.log
    exports/
    checkpoints/
      signing.checkpoint-key
      production_g......pkl
```

从一个中途文件继续，只需指定同一组、同一种子和一个新的运行名：

```powershell
python examples/cases/production_scheduling/run_quality_benchmark.py --groups directional --seeds 42 --run-id my_resumed_run --resume "完整路径/production_g......pkl"
```

正式输出与收据进入新的 run 目录；检查点继续写入原目录并复用原签名密钥。
一次恢复只能选择一个方向精修组/先导组及一个种子，不能把同一状态发给多个算法或种子。
用 `--plan` 可以先看恢复后的 Project 装配参数，不会运行求解器或生成密钥。

这与 Project 的 `--resume-from` 不同：这里恢复的是 Case 内的算法状态；
`--resume-from` 处理 Project 阶段是否需要重跑，不能代替算法续算。

## 独立 Case 的通用入口

原有 Case 命令追加以下参数即可启用：

```text
--checkpoint-dir runs/production_checkpoints --checkpoint-every 10
```

恢复时沿用原算法、问题和预算参数，再追加：

```text
--checkpoint-dir runs/production_checkpoints --resume
```

不带值的 `--resume` 选择目录中最新的检查点；`--resume PATH` 指定文件。
指定完整文件而未给目录时，使用文件所在目录。相对路径按当前工作目录解析。
独立 Case 不根据 checkpoint 猜算法构造参数；希望少重复参数时优先使用上面的具名 Project 组。

目录默认自动生成 `signing.checkpoint-key`，不需要手动设置环境变量，也不启用 unsigned 模式。
移动检查点时同时保留该文件；也可显式用 `--checkpoint-key-file PATH` 绑定原密钥。
密钥内容不进入日志、报告或 checkpoint。仓库忽略 `*.checkpoint-key`。
缺失或错误密钥会在恢复阶段拒绝，不能生成新密钥后假装恢复成功。
这些文件是本地可信运行产物，不应使用陌生来源的 pickle 检查点。

`--check` / Project build-check 只构造插件，不创建目录、密钥或检查点。
`--checkpoint-every` 必须为正数；单独给保存周期却没有目录时明确报错。
普通 Case CLI 会打印提交步数、累计求值、终止原因和最终 checkpoint 路径。

## 保存和恢复保留什么

复用 `CheckpointResumePlugin` 的签名 envelope、组件状态、Pool、Adapter、RNG、
原始反馈、证据与恢复门闸。读取文件先排队恢复，setup 后应用，普通 init hook 再观察恢复态。
没有为了 CLI 新增第二套状态机。

- 周期保存只发生于已提交逻辑步骤，不在 repair/update 半途发布状态。
- 最终状态在 teardown 前冻结；正式 Case 完成原发布事务后，才向目录镜像同一份签名字节。
- 权威交付仍是正式 Artifact 及 PublicationReceipt；本地文件提供方便的恢复入口。
- 默认保留最近 5 个文件；文件中的 g 编号沿用框架的零基 generation，实际恢复按保存进度进行。
- 恢复保留累计步数和求值，不把 `--max-evaluations` 重新当成一份免费预算。
  改变预算/算子/模型并不属于透明续算，组件配置不兼容时会拒绝恢复。
- 旧 checkpoint 只能证明其保存边界。外部强杀、检查点之后发生的工作如何结算，
  仍依赖相应运行的持久预算/证据权威，不能宣称每次崩溃都精确接在最后一条机器指令之后。

恢复报告里的求值次数包括已恢复前缀；本次进程墙钟只包括本次执行。
验证续算会额外重放一个已知后缀，这个实际成本另记，不能把两次实验合成一次耗时。

### 本轮补上的管线状态缺口

第一次大预算的恢复运行虽然也完成 106 步、2,208 次求值，但 16 份导出中有 3 份不同。
领域变异器已经实现自己的 RNG codec，原 `RepresentationPipeline` 却没有组合 codec，
因此 checkpoint 没有保存它的状态。之前在变异器尚未使用时保存的小例子不足以检出此问题。

现已由公共管线保存自身 RNG，以及明确提供 `get_state/set_state` 的算子数据。
同一个算子占据多个槽位时只保存一次，并验证别名布局；不复制锁、kernel 或任意对象图。
管线也通过正式参与者加入步骤回滚，因此取消/失败后不会单独推进其随机流。
这不证明任意第三方对象没有隐式状态：自称有状态却没有 codec 的算子直接拒绝。

含有这些状态所有者时，管线是 required checkpoint component。
旧文件缺失管线状态不能猜测恢复，必须拒绝；第一版大预算的旧 checkpoint 不作为无损续算入口。
新的回归改为“先执行实际邻域变化，再保存和恢复”，同时验证 raw、选择反馈与冻结历史引用。

## 预算耗尽不再显示 user_stop

控制器停止决定现在把原因传到 run result：

- `evaluation_budget_exhausted`：评估额度耗尽。
- `generation_budget_exhausted`：代数额度耗尽。
- `evaluation_budget_race`：共享额度竞争后已无可执行行。
- `user_stop`：明确的人工停止，保留其原义。
- `search_plan_completed`：有限搜索计划确实完成。

预算仲裁合并上限时仍取更严格的值，停止信号按“任一要求停止”合并，
不会用另一个未耗尽的预算覆盖停止。运行时依旧拒绝两个 Controller 同时拥有同一个 domain；
这里是仲裁原语的语义修正，不放宽所有权。

同一份原因进入 CLI、Solver 结果和正式 Case 输出，不能只在网页替换显示文字。

## 本次实际验收入口

大预算为 48 个 MOEA/D 方向、2 轮探索/精修/返回，每轮探索 12 步、
选 8 个方向且每方向 5 步（包含基准求值），全局最多 2,500 次求值、256 步、900 秒。
计划本身预计 106 个提交步骤，计划完成后可早于上限结束，不能为了用满预算继续多跑。

首次运行名 `acceptance_20261102_large`；它的后缀恢复发现上述 RNG 缺口，结果单独保留。
修正后完整运行名为 `acceptance_20261102_large_v2`，恢复运行为 `acceptance_20261102_large_v2_resume`。
机器可读结果与前后恢复对照记录在 `results/acceptance/production_checkpoint_20261102/`。
测试覆盖真实数据的自动签名、latest/路径恢复、错误密钥、只读 build-check、
原始目标与选择视图区分、取消回滚、共享预算及剩余预留清零。

## 最终实测结果

- 完整运行：106 个实际提交步骤、2,208 次求值，以 `search_plan_completed` 结束，未触及 2,500 上限。
- 第 90 步 checkpoint 含 2,005 次已完成求值。在新的 Project run 中恢复，实际只执行剩余 16 步和 203 次求值，累计仍为 106/2,208。
- 完整 MOEA/D 种群、完整 Pareto 档案、管线最终 RNG 状态逐项相同；16 份导出的整数排程和原始目标也全部相同。
- 原恢复输入文件 SHA 未改变。两次最终 checkpoint 的本地镜像分别与其正式封存 Artifact 的字节完全相同，发布收据已核验。
- 5 次求值的小预算 Case CLI 显示 `evaluation_budget_exhausted`；再次恢复仍是 5 次，没有重新获得 5 次额度。
- 最终 84 项契约回归、35 项 codec/checkpoint 回归通过，两组无重复，共 119 项。严格 Doctor/build 为 0 error、0 warning、10 info；未将跳过的 Catalog 审计算作已验收。

修正后的完整运行实际墙钟约 575.55 秒，Case 内约 570.65 秒；恢复运行约 29.33 秒。
完整运行前段与回归测试并行，且未控制整机背景负载，因此不能用它和首次 191.20 秒运行相减，
声称差值都是新 codec 的开销。独立的原数据管线小样本测得状态捕获约 0.68 毫秒、恢复约 4.51 毫秒；
这也不是整个框架的性能证明。

本次产量推荐为 76404，仍只代表该配置、该种子找到的可行排程，不宣称充分收敛或全局最优。
`comparison.csv` 还保留稳定、折中推荐。不同运行各自归一化的折中分数不能直接作统一尺度排名。

原始失败、后续修复、旧版不等价结果与成功复测均保留：

- `recovery_before_fix.json`：3 份导出的恢复差异。
- `recovery_after_fix.json`：修复后 16 份导出的逐项对照。
- `summary.json`：完整种群/档案、预算、签名发布与测试的机器可读汇总。
- `final_contract.xml` / `codec_guard.xml`：最终两组成功回归。

另一个回归发现 NSGA-III 的自定义 age 测试 Unit 没有继承新版 reference Unit 的 normalization 字段；
已修正测试结构继承，算法实现未在本轮更改。这些失败保留于中间 JUnit，不冒充最终全绿。
