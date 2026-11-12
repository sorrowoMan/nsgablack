# 三类算法的实际验收结果

日期：2026-10-22。Project run：`20261022T013854Z-e7140f2a1b`，group=`default`，正式执行结果为成功。

完整 Project 结果见 [project_run.json](results/project_run.json)。三个 Case 均由 Project L0 获得一线程、一个 worker 的当前有效授权，使用三个独立 Pool。每份 summary 都在原 Case finalization 事务中发布并 sealed；Project ArtifactBinding 的 publication 与 ref 已逐项核对，三个文件的 SHA256 也与收据一致。

## 同步 BO

实际四次逻辑提交、五次真实求值。真实调用次序与训练数据为：

```text
X = [0, 1, 0.5, 0.25, 0.75]
Y = [0.0625, 0.5625, 0.0625, 0, 0.25]
```

raw 最好值为 0，模型修订号为 4。模型预测和网格采集搜索未增加真实求值计数。

专项反例还验证了：两点都已真实评估、硬接纳却只交付一行时，模型仍读取完整观测；repair 后训练绑定最终候选；update 失败后的真实 Event 可在下一次同步学习一次；首次失败回到未创建 Unit 时也可保存待消费证据。正式 checkpoint 在新 Python 进程恢复，无需重跑历史 Problem。

本地观察文件：[BO summary](results/synchronous_bo/summary.json)。权威交付由 `project_run.json` 的 `artifact_bindings["synchronous_bo.summary"]` 指定，不能只凭本地文件名判断权威。

## CMA-ES

实际三次逻辑提交、十二次真实求值；每轮四个样本、两个重组父代。最终分布为：

```text
mean = [0.14506258711107878, -0.04110227992341632]
C = [[0.6256348330404585, -0.06016486336976551],
     [-0.06016486336976551, 0.6294331471920943]]
sigma = 0.2802422348709646
```

实际已评估最好候选为 `[0.15456302572242958, 0.028845562491930557]`，目标为 `0.018665697605362585`。它与分布均值分别保存，均值不冒充已评估解。

专项测试独立核对一维 `C=23/32`、二维非对角更新与非对角初始采样。只评估三行或只硬接纳两行时拒绝分布更新，保留真实成本；changed repair 在求值前拒绝。第一轮正式 checkpoint 续跑只新增八次求值，完整分布、路径、步长和样本与不中断运行一致。

本地观察文件：[分布 summary](results/cmaes_distribution/summary.json)；正式发布键为 `cmaes_distribution.summary`。

## MAP-Elites

实际一次逻辑提交、五次真实求值，最终三个格子冠军：

```text
cell (0,0) -> B=[0.4,0.4], cost=0.20
cell (1,0) -> C=[0.6,0.4], cost=0.32
cell (1,1) -> D=[0.6,0.8], cost=0.16
cell (0,1) -> empty
```

档案发生四次冠军写入（含首次占格与同格替换），最终有三个成员。五个真实观测、四次冠军写入和三个最终成员是三个不同数量。

专项测试验证跨格 repair、部分接纳、稳定 tie、精确引用、raw 反馈闭包、有限与高斯生成器、空提案等待、双实例所有权及正式 checkpoint。失败尝试不泄漏半更新档案和 Pool 视图。

本地观察文件：[档案 summary](results/map_elites_archive/summary.json)；正式发布键为 `map_elites_archive.summary`。

## 验证范围与命令

最终相关集合 **125 passed in 33.31s**：BO 17、CMA-ES 16、MAP-Elites 20、Project 3，共 56 项新增验收；原有修复、步骤事务和 checkpoint 回归 69 项。

```powershell
python -m pytest tests/test_bayesian_semantics.py tests/test_cmaes_semantics.py tests/test_map_elites_semantics.py tests/test_algorithm_semantics_project.py tests/test_proposal_repair.py tests/test_adapter_step_transactions.py tests/test_checkpoint_resume_plugin.py -q --tb=short
```

Doctor 同时检查 `default` 与 `framework-core`，均为 **0 error、0 warning、21 info；33 项 completed、0 skipped**。范围包括本 Project、三个 Case、真实构建、本地注册和 Catalog 审计；不是整个脏工作区的全仓库结论。

```powershell
python -m nsgablack project doctor --path examples/cases/algorithm_semantics --strict --build --catalog-audit --profile framework-core --format json
python -m nsgablack project doctor --path examples/cases/algorithm_semantics --strict --build --catalog-audit --profile default --format json
```

证据：[主干 Doctor](results/doctor-framework-core.json)、[完整口径 Doctor](results/doctor-default.json)、[验证汇总](results/validation.json)。

第一次综合集合曾因报告层将 ArtifactBinding 直接与 PublicationReceipt 比较而出现两项失败；算法本身和其余回归通过。修正为核对 binding.publication 与准确 ref 后，串并行 Project、报告脚本及最终 125 项集合均通过。

本次没有运行性能 benchmark 或全仓库测试，不据此比较算法效果。同步 BO 的异步/联合采集、CMA 的残缺批次累积，以及 MAP 自适应 CMA emitter 的反馈仍不在保证范围内。详细限制见 [项目说明](README.md) 和 [验收契约](../../../docs/architecture/ALGORITHM_SEMANTIC_ACCEPTANCE_CN.md)。
