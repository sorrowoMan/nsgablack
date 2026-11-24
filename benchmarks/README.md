# Quality Benchmark（自包含，不依赖 pymoo）

衡量框架多目标种群算法在标准 ZDT/DTLZ 问题上的收敛质量，输出 IGD 与 Hypervolume
（多随机种子取中位数与四分位距）。

## 为什么是自包含的

仓库原有的 `transparency_*` 与 `classical_quality` 全部依赖 `pymoo==0.6.2`
（参考前沿、HV/IGD、独立参考内核），而 pymoo 与 numpy 2.x / Python 3.13 的兼容性
存在风险，且当前环境未安装。本套件直接实现：

- 问题：`ZDTProblem`（ZDT1/2/3/6）、`DTLZ2Problem`（2 目标 / 3 目标）。
- 参考前沿：解析式（论文公式），不是框架自己生成的——避免"自己给自己打分"。
- 指标：`hypervolume`（精确维度扫描）、`igd`（复用 `nsgablack.utils.analysis`）。

指标正确性由 `tests/test_quality_suite.py` 中手算值钉死。

## 运行

```powershell
python -m benchmarks.quality_suite `
    --problems zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3 `
    --algorithms nsga2,spea2,moead `
    --seeds 11,29,47 `
    --population-size 100 --steps 100 `
    --output-dir runs/quality
```

产出 `quality_report.json` 与 `quality_report.md`（IGD 越低越好，HV 越高越好）。

三套 benchmark 同时以**标准项目脚手架**形态落位（`examples/cases/algorithm_transparency`，
复用其 Case 分发），可通过 Project 入口运行：

```powershell
cd examples\cases\algorithm_transparency
python run_project.py --group quality           # IGD/HV 质量
python run_project.py --group fusion            # 融合对比
python run_project.py --group single_objective  # 单目标 CMA-ES
```

（等价于直接 `python -m benchmarks.<suite>`，区别是走 BlackBase L0 授权与 artifact 发布。）

## 融合（多算法组合）benchmark

`python -m benchmarks.fusion_suite` 对比**顺序式混合**与各单算法在**相同评估预算**下的质量：

```powershell
python -m benchmarks.fusion_suite --pairs nsga2:moead,nsga2:spea2 `
    --problems zdt1,dtlz2_3 --seeds 11,29,47 `
    --population-size 100 --total-steps 100 --output-dir runs/fusion
```

- `hybrid = run(nsga2, T/2) -> 热启动(refine, T/2)`，最终前沿取两阶段的非支配并集。
- 对照：`nsga2` 单独跑 T 步、`refine` 单独跑 T 步。
- 公平性：三者预算均为 `population_size × T`。注意混合在精化第一步会**重新评估热启动
  种群**（约 1/T 的开销），因此混合是**带着轻微劣势**在比，赢了更有说服力。

## 单目标 CMA-ES benchmark

CMA-ES 是单目标算法，不能用 IGD/HV 评分，因此用**收敛到已知最优值**衡量
（Sphere / Rosenbrock / Rastrigin / Ackley，最优值均为 0.0）：

```powershell
python -m benchmarks.single_objective_suite `
    --problems sphere,rosenbrock,rastrigin,ackley `
    --seeds 11,29,47 --n-var 10 --steps 250
```

- 输出"找到的最佳目标值"（越低越好，趋近 0 表示收敛）。
- CMA 队列大小 `--cma-lambda` 默认自动取 `4 + 3·ln(n)`；不设则用框架默认 4。

## pymoo baseline 对拍

`python -m benchmarks.pymoo_baseline` 用**匹配算子 + 相同评估预算**对比框架与 pymoo：

```powershell
python -m benchmarks.pymoo_baseline \
    --problems zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3 \
    --algorithms nsga2,nsga3 --seeds 11,29,47 \
    --population-size 100 --steps 100
```

- 算子两侧一致：**整个体算术交叉**（10% 整体克隆 + 90% 全变量混合，rate 0.9）+
  高斯变异（sigma 0.08）。注意框架的交叉是"整个体"语义，不是 pymoo 默认的"逐变量"语义。
- 只对拍 `nsga2`/`nsga3`（pymoo 无 SPEA2；MOEA/D 的替换语义不易对齐）。
- 只覆盖 ZDT1/2/3/6 + DTLZ2（DTLZ1/4 两种实现的公式可能不同，避免不公平）。
- 这是**分布对拍**（多种子 + 同算子 + 同预算），不是逐轨迹比对（那是 transparency 套件的职责）。
- 测试 `tests/test_pymoo_baseline.py` 已钉死：框架原生问题与 pymoo 逐点一致。

**ZDT2 差距排查结论**（曾观察到框架 NSGA2 在 ZDT2 上落后 pymoo）：逐行核对后，
框架的拥挤距离、非支配排序、生存选择、锦标赛均与 pymoo 等价；差距来自两个测量
假象——(1) 低预算（1600 评估）下框架收敛略慢；(2) baseline 原用"逐变量"交叉与
框架的"整个体"交叉语义不匹配。**匹配算子后**（本模块已修）并在 6000 评估下，框架
与 pymoo 在 ZDT2 上一致（IGD 0.3645 vs 0.3525），说明框架 NSGA2 实现正确、无 bug。

## 覆盖范围与诚实声明

- 算法：`nsga2`、`spea2`、`moead`（2/3 目标均可用）+ `nsga3`（仅 3 目标问题，
  `--nsga3-divisions` 控制参考方向数，默认 12 → 91 个方向）。不兼容的组合
  （如 `nsga3 × zdt1`）会被自动跳过并写入报告的 `skipped_combinations`。
- MOEAD 说明：框架的 MOEAD 默认**不挂外部 Pareto 档案**，`get_population_snapshot()`
  返回的是分解子问题解；本套件取其非支配前沿作为 MOEA/D 的算法输出（与多数文献对
  无档案 MOEA/D 的评估口径一致）。如需显式档案前沿，可后续挂 `ParetoArchivePlugin`。
- 问题：`zdt1/2/3/6`（2 目标，n_var=30）、`dtlz2_2`（n_var=11）、`dtlz2_3` / `dtlz1_3` /
  `dtlz4_3`（3 目标，n_var=12）。
- 算子：`GaussianMutation(sigma=0.08)` + 算术交叉（rate 0.9）；MOEAD 用 DE rand/1/bin。
  这是框架现有 benchmark 的算子配方，**不是**文献标准的 SBX/多项式变异。
- 公平性：同 (seed, size, n_var) 下各算法用**相同初始种群**；评估预算对齐为
  `population_size × steps`。
- HV 参考点：ZDT 用 `[1.1, 11.0]`（沿用仓库既有 zdt1 口径）；DTLZ2 用 `[4.0]*m`
  （超出可达目标上界，避免截断）。

## 未覆盖 / 后续迭代

- **WFG / ZDT4 / DTLZ1/4 之外的变体**：WFG 参考前沿较复杂（需实现 WFG 工具包的
  `ParetoFront` 生成）；ZDT4 变量边界非均匀（[-5,5]）；DTLZ1/4 与 pymoo 的公式可能
  不同（已从 pymoo 对拍中排除，避免不公平）。
- **并发池式融合（NSGA-II + VNS 精修，SolutionPool/PoolTask 交接）**：比顺序热启动更
  接近框架的"池精修"卖点，但需仔细处理 RoleSpec/PoolTaskSpec 与多目标 VNS 的预算
  公平（现有 `examples/cases/solution_pool/pool_refinement` 可参考）。
- **DE**：框架的 DE 是标量化（`objective_aggregation="sum"`），不适合多目标质量表。
- **SBX / 多项式变异**：更接近文献标准，可加一条算子配置。

## 性能与优化记录

本套件按评估预算（`population_size × steps`）对齐，度量的是**收敛质量**（IGD/HV），
不是墙钟时间。墙钟开销的细化度量由 `transparency_costs` / `transparency_core` 的
overhead 部分负责；本节记录 2026-10 做的一次墙钟优化（NSGA2，pop=100，ZDT1，
独立进程稳态）：

| 阶段 | 墙钟 | 备注 |
|---|---|---|
| 优化前 | 79 eval/s（1.27 s/步） | cProfile 定位：快照读重哈希 ~50% + 排序 ~18% |
| ① numba 排序接线 | — | `fast_non_dominated_sort.py` 阈值 `>100`→`>20`；`units/population_features.py`、`adapters/nsga2|nsga3` 改走 `fast_non_dominated_sort_optimized`。排序本身 1401ms → 1.99ms（700×），且输出与纯 Python **逐位一致**（完美 drop-in） |
| ② 解池读路径 | — | `solution_pool._payload` 改 `read_verified_view`（blackbase 写时证书快路径，跳过内容重哈希）+ `read`（脱壳可变副本）；任何自定义/持久化 store 自动回退完整验证 |
| ③ blackbase typing 修复 | — | `blackbase/types.py` 的 `typing.Mapping/Sequence` → `collections.abc.*`（语义等价，绕开 Python 3.13 typing 的慢速 isinstance 路径；收益较小但无害） |
| **优化后** | **~138 eval/s（0.72 s/步）≈ 1.75×** | 剩余大头是本质成本：写路径摘要规范化、读路径 thaw 拷贝、CandidateBatch 一致性验证 |

测量注意：numba JIT 首次编译需数秒~数十秒（含磁盘缓存写入），同进程连跑会因内存
累积逐渐变慢——取**独立进程稳态**才可靠。
