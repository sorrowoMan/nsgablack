# 算子读取 Unit 与修复执行顺序

实现核对：2026-10-09。此契约属于 nsgablack 优化语义，不修改 BlackBase 的通用管线执行协议。

## 执行顺序

标准步骤采用以下顺序：

1. Adapter 从自己的 Unit 读取所需信息，变异或其他搜索操作生成候选副本。
2. 复合 Adapter 完成局部筛选，Solver 按评估预算截断提案。
3. 默认路径只对获准评估的行执行一次问题 repair；显式 JointRepairPolicy 可启用有限轮双侧修复验收。
4. `on_proposal_repair` 把 before/after 与原始索引交给 Unit 所有者；先重建或验证结构，再开始求值。
5. 接纳结果通过 BatchDisposition 对齐，Adapter 根据反馈更新 Unit。

`RepresentationPipeline.mutate()` 和 `mutate_batch()` 只执行变异，不隐含 repair。内置 Adapter 的 `propose` 返回待修复提案，不再手动重复调用问题 repair。初始化的 init→repair，以及 update 中对一个新内部状态的显式修复，是独立阶段，不属于同一提案阶段的重复修复。不能据此声称一个候选在整个生命周期中总共只修复一次。

repair 失败必须传播；即使 pipeline 开启 transactional，也不能返回未修复原值冒充成功。步骤事务恢复已有 Unit，已发生的外部副作用仍受各自契约约束。

修复返回普通数组时，控制面按原行/token 保留候选的 metadata，只更新数值；返回显式 UnknownState 时采用其语义内容。不能按数值相等推测身份，也不能让数值修复抹掉语义信息。

## 如何编写读取 Unit 的变异组件

通用变异组件继续实现 `mutate(candidate, context)`。需要算法结构的组件声明 `unit_inputs`，并接收显式 `unit` 参数：

```python
import numpy as np
from nsgablack.units import UnitInputSpec, POPULATION_DISTANCES
from nsgablack.representation import RepresentationPipeline

class TowardPopulationCenter:
    unit_inputs = UnitInputSpec(
        fields=("population",),
        features=(POPULATION_DISTANCES,),
    )

    def mutate(self, candidate, context, *, unit):
        population = unit.fields["population"]
        distances = unit.features[POPULATION_DISTANCES.name]
        # 示例：拥挤成员周围的提案向当前种群中心靠近。
        nearest = np.array(distances, copy=True)
        np.fill_diagonal(nearest, np.inf)
        crowded = len(population) > 1 and np.min(nearest) < 0.1
        return (candidate + population.mean(axis=0)) / 2 if crowded else candidate.copy()

pipeline = RepresentationPipeline(mutator=TowardPopulationCenter())
```

在标准 Case 的 pipeline 工厂中返回这个 pipeline，再在 `build_solver` 装配 NSGA-II 等种群 Adapter。Unit 类型必须拥有声明字段；不会因为名字相似而自动转换。

Adapter 使用 `self.mutate_candidate(control, candidate, context)`。辅助入口给候选创建副本，并从**实际调用它的 Adapter**取得 Unit；无需按名称或 context 键查找所有者。NSGA-II（含 III/SPEA2）、SA、单轨迹、VNS 和 MOEA/D 的 pipeline 变异路径已接入。VNS 读取当前 CandidateUnit，其他这些 Adapter 读取其 algorithm_unit；因此同一算子能否复用由依赖决定。

UnitInputs 只包含声明的 fields/features，以及 unit_id、schema 和依赖内容 revision；数组与容器脱离并只读，不暴露 Solver、Provider 或可写 Unit。相同 unit_id 不是缓存或绑定的索引。revision 表示依赖内容，不是跨系统身份凭证。

读取 objectives/violations 等直接反馈字段时，声明 `feedback_view="selection"`；读取 UnitFeature 时使用该特征自己的反馈声明。依赖缺失、反馈过期、schema 不符都必须报错。可选 `schema=...` 要求精确 schema；省略时只检查声明字段，允许较丰富的 Unit 复用算子。

手动调用 `pipeline.mutate` 须传入 `unit=spec.capture(owner_unit)`；批量调用须传入与行数对齐的 `units`。批量 Unit 变异按行调用正式单点接口，目前没有专用向量化 Unit 变异协议。算子内部 TypeError 不会导致丢掉 Unit 参数重试。

当前显式 Unit 输入接在 `RepresentationPipeline(mutator=...)` 的叶组件与 Adapter 辅助入口。通用 BlackBase slot runner 和任意第三方 mutator wrapper 不会自动转发 UnitInputs；不要把它偷偷塞进 context。自定义 Adapter 若使用该入口，应声明 `uses_pipeline_mutation=True`，必要时覆盖 `get_operator_unit()`。

## 多个 Adapter 是否需要各自一套 Pipeline

不需要。问题侧的初始化、约束修复、编码和解码可以由同一个 `RepresentationPipeline` 提供。Adapter 根据搜索需求选择其中的变异算子，Unit 依赖由实际调用该算子的 Adapter 提供。算法结构仍通过各 Adapter 的 `UnitBinding` 构建；两种绑定都不要求复制问题管线。

同一算子可以被多个 Adapter 复用，只要各自 Unit 满足依赖。不同种群 Adapter 也可以选不同算子。Adapter 类型与 Pipeline 不是一对一关系，不能仅凭类型名称自动匹配算子。

单算法或共享算子时，仍用 `RepresentationPipeline(mutator=...)`。需要不同算子时，注册 `mutation_operators` 并在装配处选择：

```python
from nsgablack.adapters import NSGA2Adapter, SimulatedAnnealingAdapter, CompositeAdapter

class TrajectoryNeighbor:
    unit_inputs = UnitInputSpec(fields=("current",))

    def mutate(self, candidate, context, *, unit):
        # 示意一个确定性邻域方向；领域项目在 pipeline/ 中定义自己的算子。
        return unit.fields["current"].copy() - 0.1

# 以下放在标准 Case 的装配函数；initializer、problem_repair 由 pipeline 工厂提供。
pipeline = RepresentationPipeline(
    initializer=initializer,
    repair=problem_repair,
    mutation_operators={
        "population": TowardPopulationCenter(),
        "trajectory": TrajectoryNeighbor(),
    },
)
population = NSGA2Adapter()
trajectory = SimulatedAnnealingAdapter()
population.set_mutation_operator("population")
trajectory.set_mutation_operator("trajectory")
adapter = CompositeAdapter([population, trajectory])
# 将 adapter 与这一份 pipeline 装配给同一个 ComposableSolver。
```

`set_mutation_operator(None)` 使用默认 `mutator`。显式名称不存在时直接报错；仅注册具名算子而没有默认项时，消费者必须选择名称。不要在运行期间临时调用 `pipeline.set_mutator(...)` 给不同子 Adapter 换算子，也不要把完整 Pipeline 挂到每个 Adapter 上。

选择绑定在实际执行变异的叶 Adapter；Role/Composite 等容器转发到叶，不能在容器上绑定一个名称并假定自动广播。没有调用管线变异的算法（例如 DE 自带的差分提案）不需要该绑定。自定义 Adapter 使用前述辅助入口并声明 `uses_pipeline_mutation=True`。

手动调用可用 `pipeline.mutate(x, context, operator="population", unit=inputs)`；`mutate_batch` 的整批选择一个 `operator`，仍为每行提供对齐的 `units`。具名算子使用现有 kernel 执行普通变异，Unit 叶算子使用显式输入；共享 repair 始终在控制面单独执行。

注册表在构造时复制并只读；算子对象本身不会被克隆。共享同一个有状态算子意味着共享其状态和随机流，绑定不同名称也不会使同一对象自动隔离。需要独立状态时显式创建不同实例；需要恢复的状态仍须走正式 checkpoint/事务契约。不同算子间的选择互不修改，但这不承诺任意算子都是线程安全的。

具名算子纳入 context contract、随机种子设置、`pipeline.describe()` 与运行表面组件索引。Adapter 的 Unit 装配报告显示所选名称。绑定是装配配置，不是随步骤变化的搜索状态；恢复时必须重新装配一致的配置，当前检查不证明任意算子实现或装配内容等价。

## repair 与 Unit 的关系

独立的 ProblemRepair / UnitRepair、临时结构与共同验收见 [共同修复契约](JOINT_REPAIR_CN.md)。下述 owner 对账是其中一部分，不能等同于完整的双侧可行性验证。

问题 repair 处理候选的约束；Unit 所有者验证算法结构。例如修复后的有限差分点仍须沿原坐标方向，信赖域点仍须位于当前区域，A* 的父边须可解释。Unit 校验失败时终止本次步骤，不能隐式放宽算法条件。

`get_proposal_contexts(count, context)` 返回按原始提案行对齐的调用上下文。复合 Adapter 按原来的 ranges、局部 BatchDisposition、角色和 StrategyTask 进行路由；MOEA/D 保留每行的子问题/权重/邻域模式。预算裁剪后才取对应前缀。它是调用局部数据，不写入共享 ContextStore。

支持 `repair_batch(..., contexts=...)` 的管线一次接收这组上下文。只支持单一共享 context 的旧批量接口走正式单点 repair，避免丢失每行所属任务；不在执行失败后重试其他签名。

## 迁移与验证

- 独立使用 pipeline 时，需要修复结果应显式调用 `repair(pipeline.mutate(...))`，批量同理。
- 自定义 `propose` 应移除手工问题 repair；需要结构对账的逻辑放入 `on_proposal_repair`。直接调用 propose 得到的是提案，不能当成已修复或已评估结果。
- `production_scheduling` 的标准 Case 也已移除提案阶段的重复 repair。
- Doctor 的 `unit-operator-contract-invalid` 检查声明、函数签名及已存在消费者 Unit 的依赖，且不执行特征函数。尚未初始化的 Unit、第三方任意 Python 副作用仍须运行时检查和行为测试。
- 多算子场景中，Doctor 检查每个消费者实际选择的算子；名称不存在、缺默认选择、选择了不兼容的 Unit 依赖都会报错，不再将默认算子的依赖强加给所有 Adapter。绑定到不使用管线变异的 Adapter 也会拒绝。
- `tests/test_unit_operator_inputs.py` 验证非幂等修复次数、预算、只读依赖、相同 ID 多实例、角色上下文、异常传播和 Doctor。结果记录于 `artifacts/audit/unit-operators-20261009/`。
- `tests/test_shared_mutation_pipeline.py` 覆盖异质嵌套组合、共享修复、按实例选择、缺失/错误绑定、批量与重叠调用；验证记录在 `artifacts/audit/shared-pipeline-20261009/`。
