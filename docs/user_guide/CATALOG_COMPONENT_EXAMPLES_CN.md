# 在组件目录中查看和验证用法

在 Catalog 搜索组件键或名称，选中条目后查看“用法”。目录中同时有装配片段和完整教学说明；字段存在、源码已核对，并不保证已讲清楚怎么使用。完整教学应从一个具体需求开始，交代组件装入后怎么执行、数据和反馈往哪里走、如何运行已有正式Case，以及怎样读取结果。

例如[CompositeAdapter教学Case](../../examples/cases/catalog_recipes/cases/composite/README.md)说明两个独立种群如何共同送评、各自保留成员，并和“GA后接VNS精修”区分。该例子的正文代码与正式Case装配代码做一致性检查；它不是单纯的`solver.set_adapter(...)`构造演示。

默认左侧为名称与用途列表。右侧“用法”先说明代码放在哪个Case工厂、应准备什么，再展示可复制代码、接入步骤和结果检查。第一次接入可展开“先创建一个标准Project”，完整两条路线见[第一次装配](CATALOG_FIRST_ASSEMBLY_CN.md)。参数和运行收据按需展开；接口页保留方法、契约与原始声明。

详细教程下方的“还能怎样改”按使用目的展示变体，分别说明修改文件、完整替换代码、行为变化和限制。主用法需要多个文件时，全部必要代码块都会先展示，变化用法另行展开。不要把不同变体的代码不加区分地叠加。

本轮新增的[解池与搜索编排应用](../catalog_usage/POOL_AND_ORCHESTRATION_APPLICATIONS_CN.md)覆盖七个条目：读取精确成员、从最终生存者选精英、成员档案、方向视图抽取、递归精修、工作区、初始化与竞争任务，以及有限串并行和完成条件。[ML组件应用](../catalog_usage/ML_COMPONENT_APPLICATIONS_CN.md)覆盖十二个条目：LearningSolver、数值数据、线性模型布局，以及点、分类、校准和区间Head。每个ML条目独立给出真正会调用新工厂的builder；改变输出含义时，同时交代Problem、数据和搜索器的配套修改。这十九条合计三十六种变体，均为源码核对的操作说明，不能当成改造后的训练运行记录。

AI详细教程直接保存在既有知识数据库，按发布源码摘要和整理版本匹配；无需把每次生成结果抄回TOML。新整理会另发一次独立源码审阅，核对真实调用者、配置分支、结果入口与变体前提；未通过或证据不足的草稿不发布。页面浏览只读数据，不调用模型。AI源码审阅仍不能证明示例已经运行或算法效果更好，实际运行收据继续单列。优质人工教程保留在主用法中，AI可以补充变化用法。

关系页可查看目录明确声明的配套，以及实际用法中创建/调用的组件。每条调用关系提供源码位置，点“查看用法”进入目标组件，再用“返回上一个”回来。上下文/Artifact/阶段的键匹配是另一类关系，不能据此推断所有组件能直接互换。

字段齐全、源码核对通过，只说明有来源可追溯的片段。若缺少具体调用前提或结果检查，页面会标出待补充，不再用“得到已装配组件”等泛化句冒充完整使用说明。

不要只复制 `import` 或根据类名猜装配方式。例如，`SurrogateControlBias` 虽然保留旧类名，实际返回控制更新映射，不是标量评分；目前也没有正式自动消费者。目录将其归入工具并解释边界。普通软评分请使用对应评分 Bias 或 `CallableBias`。

## 更多算法的完整应用

- [进化搜索](../catalog_usage/EVOLUTIONARY_ALGORITHM_APPLICATIONS_CN.md)：NSGA-III、SPEA2、DE、CMA-ES 与 MAP-Elites；分别说明最终成员、完整 cohort 与分格冠军从哪里读取。
- [局部搜索](../catalog_usage/LOCAL_SEARCH_APPLICATIONS_CN.md)：SA、Gaussian、梯度优化器、Pattern Search 与 Trust Region；包含停滞恢复、池交接和方向精修。
- [贝叶斯与图搜索](../catalog_usage/BAYESIAN_AND_GRAPH_SEARCH_APPLICATIONS_CN.md)：BO 的模型、采集与观测；A*/MOA* 的根、边、标签及目标结果。新文件需要配套包入口时一并给出，不只给孤立构造代码。

这些章节提供基础接线和可改造的用法，代码按当前来源核对；构造检查、算法实际运行和效果评价分别记录。后端章节还区分能力声明、签名描述与可调用方法：显式指定后端缺能力时会失败，只有省略 preferred 才搜索匹配者。源码更新后，旧 AI 笔记须按新摘要重新审核，历史记录不会冒充当前教程。

## 偏好、评估与运行插件

- [Unit 与 Bias](../catalog_usage/UNIT_AND_BIAS_APPLICATIONS_CN.md)：六个独立用法，区分只读结构、整体多样性、候选相对 Unit 的偏好、软评分组合、禁忌记忆和动态惩罚。每章按 Bias 实现、报告插件和薄装配入口分别给代码。
- [评估 Provider](../catalog_usage/EVALUATION_PROVIDER_APPLICATIONS_CN.md)：代理、多保真、Newton 与 Broyden，说明什么时候可以接管求值、怎样保留原始约束与指标、如何区分预测/真实或低/高保真。近似评估须显式允许，Provider 不重复施加 Bias 或给 Solver 再计一次求值。
- [运行插件](../catalog_usage/RUNTIME_PLUGIN_APPLICATIONS_CN.md)：checkpoint、模块报告、性能分析和决策轨迹。每章指出实际挂载点、配置启用分支、输出文件与可信恢复边界；观察文件不冒充最终权威成功。

## 如何读状态

详细用法中的文件说明、代码与后续解释按原文衔接显示。第一段代码前会标明所属文件，多文件接线不再只剩连续代码；数学幂和关键字展开（如 `x**2`、`factory(**kwargs)`）保持原样。

- **用法示例**：针对该组件的代码和说明，已绑定发布源码；不表示完整 Case、训练或外部后端已经运行。
- **已运行示例**：对应相同发布源码的正式 Project 已成功运行，页面另列实际输出、时间和退出码。
- **示例待验证／入口引用**：只找到了导航、文档或尚无运行记录的 Case，不能凭这个标签推断算法效果。

普通装配片段不会再被一个泛化的入口引用遮住。多行 Python 保留缩进和空白行，Markdown 用法按说明与代码围栏正常排版；非 Python 的流程关系显示为文本。

## 三份逐项说明

- [nsgablack：280 项](../catalog_usage/NSGABLACK_COMPONENT_USAGE_CN.md)：Adapter、Unit、Pool、算子、Bias、Plugin、工具，以及文档和正式示例入口。
- [mlblack：数据、Head、Codec、模型、管线和 preset](../catalog_usage/MLBLACK_COMPONENT_USAGE_CN.md)：140 项，按实际接口的别名关系共享 121 个片段。
- [mlblack：Problem、Trainer、Provider、控制与后端](../catalog_usage/MLBLACK_EXTRA_COMPONENT_USAGE_CN.md)：137 项，包含 26 个动态后端／能力条目。

完整运行仍由标准 Project/Case 和 L0 管理。组件级调用验证、preset 构造和完整训练是不同的检查，不合并成“全部算法已验证”。

## 一个评分用法的读法

下面只演示组件调用；在正式 Case 中将该 BiasModule 按原装配入口传给 Solver。

```python
import numpy as np
from nsgablack.bias import BiasModule

module = BiasModule()
module.add(lambda candidate: float(candidate.sum()), weight=0.25, name="linear")
raw = np.array([10.0, 20.0])
selected = module.compute_bias_vector(np.array([1.0, 2.0]), raw, context={})
print(selected)  # [10.75, 20.75]
print(raw)       # [10.0, 20.0]，原始评价保留
```

若卡片要求已有 `solver`、`data_view`、模型或 ResourceContext，它是在对应 Case 位置使用的片段；这些前置不能省略，也不能凭空用占位对象替代。

## 维护者的全量检查

示例构建使用显式的完整 Catalog 快照，包含动态 Provider 条目；不再仅扫描 TOML。发布时逐组件检查是否有专门用法、必需说明是否齐全、Python 语法是否有效，并验证页面不调用模型、构建 Unit 或运行 Solver。下面在 nsgablack 仓库根目录执行，完整三仓示例须启用 ML 公共 Catalog provider。

```python
from pathlib import Path
import os
from nsgablack.catalog.registry import get_source_catalog
from nsgablack.catalog.examples import build_example_index, load_example_index
from nsgablack.catalog.example_audit import audit_usage

os.environ["NSGABLACK_CATALOG_PROVIDERS"] = "mlblack=mlblack.catalog.registry:get_catalog"
entries = get_source_catalog(profile="default").list()
roots = {name: Path("../") / name for name in ("nsgablack", "blackbase", "mlblack")}
index_path = Path(".pytest_cache/catalog-examples.json")
build_example_index(roots, index_path, catalog_entries=entries)
report = audit_usage(load_example_index(index_path), entries)
assert report["complete_usage"]
```

这项检查证明用法覆盖和可展示性。实际运行收据仍需独立运行正式 Project 生成，不能手工补一个 `executed` 标记。
