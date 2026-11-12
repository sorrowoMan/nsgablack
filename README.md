# NSGABlack

**面向优化算法设计、组合与应用的 Python 框架。**

定义问题，装配搜索组件，再用解池与执行计划组织种群搜索、局部精修、共享档案和嵌套求解。
NSGABlack 将候选解的管理、算法结构与搜索决策分开，让算法代码集中描述“怎样搜索”，
并由公共运行机制维护候选身份、反馈对齐、预算和恢复。

[快速开始](#快速开始) · [核心设计](#核心设计) · [装配示例](#装配示例) · [完整案例](#完整案例) · [文档](#文档)

> 本页介绍[当前开发分支](https://github.com/sorrowoMan/nsgablack/tree/codex/framework-review-20261112)的能力，
> 查看实现与运行示例请使用该分支。

## 可以用它做什么

- **修改算法的一部分**：替换初始化、变化或选择规则，扩展成员年龄等状态，保留其余算法流程。
- **组合多种搜索方法**：全局搜索后局部精修，多个种群协作，按阶段、停滞条件或局部额度切换算法。
- **组织候选解的流动**：从池中选择、分组、聚合，维护精英或参考集合，再交给下一段算法。
- **构建完整优化应用**：把问题、算法、运行资源、检查点与结果组织为独立的 Project / Case。

例如，一段混合搜索可以这样组织：

```mermaid
flowchart LR
    A[初始候选] --> P[解池]
    P --> G[种群搜索]
    G --> E[精英集合]
    E --> L[局部精修]
    L --> R[结果集合]
    R -->|返回竞争| G
```

种群算法决定哪些成员留下，局部算法按自己的规则精修。
两者通过候选引用和池任务交接，各自维护自己的算法状态。
[GA → VNS → GA 的完整装配](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/assembled_ga_vns/README.md)已经提供对应的标准 Project。

## 快速开始

### 安装开发源码

当前开发版本为 **0.4.1**，要求 **Python ≥ 3.10**。
当前源码与 `blackbase` 的开发接口协同演进；运行下面的示例，需要先准备与本快照匹配的
[BlackBase 源码](https://github.com/sorrowoMan/blackbase)。配套共享接口还有未发布的开发改动，
下面的安装步骤面向已有匹配源码的开发环境；目前尚未提供可公开复现全部新功能的依赖版本组合。

假设 `blackbase/` 与 `nsgablack/` 并排放置，在 `nsgablack` 根目录执行：

```powershell
python -m pip install -e ../blackbase
python -m pip install -e .
```

算法对照实验按需安装：

```powershell
python -m pip install -e ".[benchmark]"
```

### 创建并运行自己的项目

```powershell
python -m nsgablack project new my_project
cd my_project
python -m nsgablack project add-case search --type solver --framework nsgablack
python run_project.py --check --build-check
python run_project.py
```

生成的 Case 包含可运行的二维平方和问题、候选管线和 NSGA-II，默认执行两次逻辑提交。
`--check --build-check` 用于核对实际装配与生效的资源配置。
下一步可依次替换问题、搜索组件和项目编排，见[从第一个 Project 开始](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/standard_scaffold_tutorial/01_create_and_run.md)。

### 先跑一个现成组合

在仓库根目录执行：

```powershell
# 两个 GA 各自维护种群，Router 统一维护共享精英档案
python examples/cases/pool_workflow_pilot/run_project.py --group parallel_archive

# 两轮 GA → VNS → GA，按阶段计划交接精英与精修结果
python examples/cases/assembled_ga_vns/run_project.py --group plan
```

第一个例子是同一 Solver 内的逻辑并行协作；Project 级并行与跨 Case 调用另有独立示例。

## 核心设计

框架按 **Problem → Pipeline → Unit → Adapter → Bias → Plugin** 分工，Pool 贯穿候选管理与交接。
这是职责关系，不是固定的六阶段执行顺序。

- **Problem**：定义原始目标、约束和评估含义。
- **Pipeline**：提供候选初始化、表示变换与问题侧修复等数据处理能力。
- **Pool**：组织候选版本和引用集合，提供选择、分组、合并及入池操作。
- **Unit**：保存算法需要的结构、成员属性与关系，例如种群、搜索节点或局部区域。
- **Adapter**：拥有搜索决策，按需创建 Unit，提出候选并消费反馈。
- **Bias**：表达选择偏好，同时保留 Problem 的原始求值与约束证据。
- **Plugin**：参与日志、评估后端、检查点、观察和结果发布等生命周期能力。

Solver 将这些组件装配起来，安排评估、接纳、更新和提交。
初始化、变化、选择、修复是可装配的行为类别，各算法按自己的流程使用它们。

### Pool 管候选，Unit 管算法中的关系

同一个候选可以被多个算法引用，但它在不同算法中的排名、年龄或方向关系可能不同。
Pool 保存精确的候选版本；Unit 保存“这个候选在本算法中是什么成员”。

因此，一个种群淘汰某个成员，不会顺带删除其它算法仍在使用的候选。
同一候选占据多个槽位时，也可以保留各槽位自己的属性。
读取已有解保留身份，变化产生新提案；候选数值相等不代表它们是同一个解。

普通变化规则可以直接复用基础 Unit。
需要增加算法状态时，再通过 `UnitBinding` 扩展结构及成员维护规则；未启用的算法无需提前构造 Unit。

### 池内操作与外层编排分别表达

Pool 操作描述“取哪些解、如何分组、送到哪个区域”；
Router、Chain 与 SearchPlan 描述“哪个算法何时执行、运行多久、何时等待或交还结果”。

例如，有限循环可以用已有计划表达，而无需手算全局代数：

```python
from nsgablack.adapters import repeat, serial, stage

plan = repeat(times=2, body=serial(
    stage("ga", steps=2, label="ga"),
    stage("vns", label="vns"),
    stage("ga", label="return"),
))
```

这是执行计划片段；算法实例、池输入和结果返回仍需显式装配。
完整代码见 [GA / VNS 的阶段组合](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py)。

## 装配示例

下面是 Case 的 Adapter 工厂片段：定义一条完整变化规则，
沿用 NSGA-II 的生存选择，再从本轮最终成员中维护一个精英集合。

```python
from nsgablack.adapters import NSGA2Adapter, Pool


def change(request, *, rng):
    center = request.parents.mean(axis=0)
    return center + rng.normal(0., 0.1, center.shape)


def maintain_elite(request, *, rng):
    elite = request.members.top(
        20, key=lambda pool: pool.raw_feedback()[0][:, 0]
    )
    Pool(parent=request.members, name="elite").inject(
        elite, replace=True
    )


ga = NSGA2Adapter(
    population_size=100, offspring_size=80, change=change
)
ga.set_pool_maintenance(maintain_elite)
```

这里的变化是“父代均值＋高斯扰动”，精英规则明确采用原始第一目标；
多目标 Pareto 留存需要选择相应规则。自定义 `change` 接管完整变化，不额外叠加默认交叉与变异。

将 `ga` 交给本 Case 的 Solver 后，候选继续经过正式预算、评估和接纳流程。
具名池的变更随原步骤一起提交；失败时回滚工作状态，已发生的求值成本保留。
该片段不包含 Problem / Pipeline 的定义，完整工程入口见 [Pool 工作流 Project](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/pool_workflow_pilot/README.md)。

同样的维护入口也可以绑定到 Router，在子更新完成后统一归并共享档案。
需要分别读取不同算法的成员属性时，使用 `request.members_by_owner`。
更多真实接口与支持边界见 [Pool 手册](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/POOL_API_REFERENCE_CN.md)。

## 完整案例

按想实现的事情选择入口：

- **选择、变化、精英分流与共享档案**：[Pool 工作流](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/pool_workflow_pilot/README.md)。
- **种群搜索与局部精修**：[GA + VNS](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/assembled_ga_vns/README.md)。
- **方向子问题与递归精修**：[MOEA/D 嵌套投影](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/assembled_moead_nested/README.md)。
- **模型观测、整批更新与格子档案**：[同步 BO、CMA-ES、MAP-Elites](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/algorithm_semantics/README.md)。
- **生产排程及供料调整**：[生产排程](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/production_scheduling/README.md)、[嵌套到料调整](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/supply_adjustment_nested/README.md)。
- **多 Case、资源与组合装配**：[综合装配工作台](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/assembly_workbench/README.md)。
- **效果、语义和额外开销的对照**：[算法透明性实验](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/algorithm_transparency/README.md)。

已有 Adapter 涵盖 NSGA-II/III、SPEA2、MOEA/D、DE、VNS、SA、A*、信赖域、梯度及模型驱动搜索等。
各算法保留自己的状态与比较规则，支持的操作和组合方式以各组件说明为准。

## 项目组织与框架栈

```text
my_project/
  project_config.py          # 跨 Case 编排与资源需求
  run_project.py             # Project 运行入口
  cases/
    search/
      build_solver.py       # Case 装配入口
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

每个 Case 是独立运行和被外层调用的组合单元；Project 负责跨 Case 的执行与资源授权。
同一套脚手架也用于内外层嵌套，输入、结果和 Artifact 通过正式边界传递。

NSGABlack 与两个独立项目协作：

- [BlackBase](https://github.com/sorrowoMan/blackbase)：共享项目编排、资源授权、Context / Snapshot / Artifact 与公共运行协议。
- **NSGABlack**：优化问题、候选搜索、算法结构、多目标选择和求解结果。
- [MLBlack](https://github.com/sorrowoMan/mlblack)：ML 数据、模型语义、训练、评估和模型 Artifact。

使用优化搜索无需先引入 MLBlack。需要将模型训练或推理接入优化任务时，再通过正式 Case / Provider 能力组合。

## 组件发现与文档

查找现有组件及其装配说明：

```powershell
python -m nsgablack catalog search vns --profile framework-core --limit 5
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

Catalog 提供组件职责、参数、示例和关系说明；工作区与 AI 引导用于辅助查找、编辑和装配。
AI 建议仍需经过构建与运行验证。

- [文档入口](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/README.md)与[标准脚手架教程](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/standard_scaffold_tutorial/README.md)
- [算法操作装配边界](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md)
- [Pool 接口与实例](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/POOL_API_REFERENCE_CN.md)
- [自然搜索编排](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/NATURAL_SEARCH_PLANS_CN.md)
- [Unit 构建与扩展](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/guides/ALGORITHM_UNITS_CN.md)
- [运行契约与恢复](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/RUNTIME_CONTRACTS_CN.md)
- [Catalog 使用](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/architecture/CATALOG_USAGE_CN.md)
- [全部示例](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/examples/cases/README.md)

## 开发状态

当前为开发快照。仓库已提供可运行的核心框架、标准案例和专项测试；
不同算法与组合的支持程度有所区别，测试结果只对应具体版本、路径和配置。

当前验证基于匹配的本机开发依赖，尚未完成全部组件的干净环境安装与全仓验收。
最近一次提交的检查结果和已知问题见 [开发快照验证说明](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/docs/research/VALIDATION_STATUS_20261112.md)。
跨独立 Case 的异步归并、部分高级组合的使用体验和更多性能对照仍在完善。

## License

[MIT](https://github.com/sorrowoMan/nsgablack/blob/codex/framework-review-20261112/LICENSE)
