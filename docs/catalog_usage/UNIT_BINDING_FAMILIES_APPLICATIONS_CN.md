# Unit构建绑定：保留真实算法，只明确结构与codec的消费者

所有配方仅按源码/AST/接口核对，未运行算法、模型或Project。每节引用的基础配方是该节的一部分：先保存完整正式Project/Case文件，再进行明确替换；不是把一个UnitBinding放进任意算法。结构规则可以装配，运行Unit仍由所属Adapter按需创建。

## binding.vns · 候选Unit与邻域Unit是两个不同槽位

**什么时候用：** VNS需要保存候选本体，同时保存k对应的尺度表；想在装配时明确谁负责构建/恢复这两种结构。CandidateUnitBuilder不是NeighborhoodUnitBuilder，两者不能互换。

**先准备什么：** 《CANDIDATE_LAYOUT_APPLICATIONS_CN.md》的 `repr.continuous` 与 `layout.shared_case` 完整配方；独立catalog_recipes副本，Case composite，三维非负单纯形候选、VNS、正式Project/L0与LayoutReport。保留该例的全部Problem/Pipeline/报告。

**放在哪：** 将该例build_solver.py原完整内容保存为同Case的base_solver.py，然后用下列代码完整替换build_solver.py。相对导入仍在同包，正式run_solver.py只调用新规范入口，不新建第二个运行器。

**接入步骤：** 在原builder返回实际实例后、任何setup/候选生成前绑定规则。这里只读检查声明，禁止为观察而调用ensure_neighborhood_unit。

```python
from nsgablack.representation import CandidateUnitBuilder, NeighborhoodUnitBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    search = solver.adapter
    search.set_unit_binding(UnitBinding(CandidateUnitBuilder()))
    search.neighborhood_binding = UnitBinding(NeighborhoodUnitBuilder())
    search.validate_unit_bindings()
    if search.current_unit is not None or search.neighborhood_unit is not None:
        raise ValueError("assembly must not create VNS runtime structures")
    return solver
```

CandidateUnitBuilder保留同一候选语义和身份；fresh/spawn/refresh不负责repair或送评。NeighborhoodUnitBuilder构造scales，不拥有k切换决策；VNS提供base_sigma/scale/max_sigma/k_max，恢复走dump/restore，不重新采样或推导另一份尺度表。

**怎样判断接对：** 装配检查通过且两个运行结构仍None；执行后本次layout.json继续交付该VNS最终已评估点/精确ref/raw反馈，current_score与候选对齐。get_state中current_unit与neighborhood_unit分别有codec载荷，未激活时允许None；读取声明不应改变它们。

**运行入口：** 沿基础配方副本的 `python run_project.py --group default --check --build-check`，再同入口 `--group default`；不把build-check当结构恢复验收。实质变体沿该基础例同步改变Problem总量和ProjectionRepair总量，两槽绑定保持；不能在builder中偷偷做投影。

## binding.trajectory · 一个模型参数候选与一条搜索轨迹

**什么时候用：** GaussianSearch需要current/best及关联反馈；想看见它维护的是TrajectoryUnit，而非把ML模型Codec当优化器状态。

**先准备什么：** 《ML_CORE_CONTRACT_APPLICATIONS_CN.md》的core.contract.model/host/run完整Case，独立mlblack catalog_codec_demo副本，三坐标[w0,w1,b]、Gaussian、NumPy/两特征回归和正式typed JSON发布。无需Torch或JAX。

**放在哪：** 将该例原build_solver.py移为base_solver.py，新规范入口如下。原Head/Representation/Problem/观察器均保留；下面没有创建模型或搜索Unit。

**接入步骤：**

```python
from nsgablack.representation import TrajectoryUnitBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(TrajectoryUnitBuilder()))
    solver.adapter.validate_unit_bindings()
    if solver.adapter.algorithm_unit is not None:
        raise ValueError("trajectory must remain lazy during assembly")
    return solver
```

**怎样判断接对：** core.json仍是一个三参数最佳已评估模型；轨迹单元保存current/best/candidate_feedback，current与best的反馈依赖有版本，不能因数组同值就借用旧分数。codec为v2，不能假定旧v1状态自动兼容。ML候选metadata由表示解释，Unit不拥有数据集或模型会话。

**运行入口：** 同基础Project的run_core_and_report.py与L0；本章未执行。基础配方“关闭额外状态捕获”变体只减少结束观察，Trajectory本身的正式checkpoint不因OBSERVE_STATE开关丢失。

## binding.poll · 方向/探针与修复后位移不能只保存一个当前点

**什么时候用：** PatternSearch按坐标发出正负探针，需要结构同时保存current、directions、probes、displacements与关联反馈。

**先准备什么：** 《LOCAL_SEARCH_APPLICATIONS_CN.md》的adapter.pattern_search完整配方，独立assembled_parallel_cases副本、Case sa_valley、二维谷地/ClipRepair(-4,4)、原Project/L0。该Case实际算法已换PatternSearch，另一个DE Case仍独立。

**放在哪：** 原builder同包保存为base_solver.py，新build_solver.py如下；保留完整Pattern工厂和Problem/Pipeline。

**接入步骤：**

```python
from nsgablack.representation import PollUnitBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(PollUnitBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

PollUnitBuilder的initialize与poll都是必要操作；poll的dimensions由Adapter选择，builder形成正负方向和探针标签，不自己决定成功/扩步。不能用只支持initialize的TrajectoryUnitBuilder来“少记几个字段”。修复改变坐标后，displacements由Adapter对账。

**怎样判断接对：** 本次sa_valley结果仍两维/一目标；局部step_size与四个原提案探针对应，但部分预算后不强求仍有四行。get_state的algorithm_unit含探针/位移，最佳结果用get_pool_refinement_results，不取尚未评估点。恢复不能重新随机挑dimensions。

**运行入口：** 原正式run_project.py，保留基础例的“坐标搜索后SA继续精修”变体与候选交接规则；原针对SA每步一行的run_and_report计数不再适用。这里只新增绑定，不宣称运行或恢复通过。

## binding.parameters · 梯度坐标、Adam矩和模型布局分别是谁的

**什么时候用：** GradientOptimizer消费三坐标反馈，需要first_moment/second_moment随参数形状维护；不把矩状态塞入模型Codec或共享context。

**先准备什么：** 《ML_CORE_CONTRACT_APPLICATIONS_CN.md》的core.functional.gradient与core.contract.run完整JAX Case，原Project/L0，已有可选JAX依赖。模型候选顺序[b,w0,w1]，l2=0，真实函数梯度；未安装/执行依赖。

**放在哪：** 原builder同包保存为base_solver.py，新规范入口如下。参数表示、Problem梯度与正式Artifact蓝图不改。

**接入步骤：**

```python
from nsgablack.representation import ParameterUnitBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(ParameterUnitBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

ParameterUnitBuilder必须支持initialize/optimizer_slots；Adapter请求slots时传形状，builder建立成对零矩。SGD不因结构中有矩字段就使用Adam；基础例config的gradient.adam变体才消费它们。矩必须同形，不能复用另一个模型布局的checkpoint。

**怎样判断接对：** 本次core.json含3参数/同形JAX梯度信号与正式模型引用；update保存的后继可能未评估，结果仍取Solver incumbent。Unit codec保留必要矩状态，模型蓝图不声明自己含优化器。

**运行入口：** 完整副本run_core_and_report.py；两次method变体分别建立新运行，不把旧SGD状态当新Adam。静态装配说明不是梯度数值或恢复验收。

## binding.reference_population · 参考方向是结构，生态位选择是算法

**什么时候用：** NSGA3需要Population成员及reference_points，希望明确builder为何必须提供reference_directions操作。

**先准备什么：** 《EVOLUTIONARY_ALGORITHM_APPLICATIONS_CN.md》的adapter.nsga3完整新Project配方，Case search，二维候选/三个平方距离目标/12成员、divisions=3、正式members报告和Project L0。

**放在哪：** 原规范builder保存为base_solver.py，再完整替换build_solver.py；原adapter工厂和其它文件不改。

**接入步骤：**

```python
from nsgablack.representation import ReferencePopulationBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(ReferencePopulationBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

**怎样判断接对：** 本次members.json仍12行、每行3raw目标；reference_points依据目标数/整数divisions构造，不把方向数当种群大小。builder显式兼容基础Population schema不代表任意PopulationBuilder都反向兼容ReferencePopulation；NSGA3需要的operation不满足会拒绝。初值与成员维护仍走repair/evaluate/admission与Population成员协议。

**运行入口：** 原新Project的run_project.py，--check --build-check只看声明；原“双孩子交叉”变体继续消费同一成员结构，构建器不负责交叉选择。本章不重算性能或声称参考方向覆盖保证。

## binding.differential_population · DE的目标槽位与试探行需要一起恢复

**什么时候用：** DE必须保持population与pending目标索引，不能只复用普通三数组丢掉trial对应关系。

**先准备什么：** 《EVOLUTIONARY_ALGORITHM_APPLICATIONS_CN.md》的adapter.de完整配方，独立assembled_parallel_cases副本，de_bowl二维单目标、12成员/12批、原initializer/repair与Project L0。

**放在哪：** 将de_bowl原builder保存为base_solver.py，再保存如下规范入口。原adapter/search.py按完整DE配方保留。

**接入步骤：**

```python
from nsgablack.representation import DifferentialPopulationBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(DifferentialPopulationBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

**怎样判断接对：** 读本次正式de_bowl结果及原精确成员接口；pending_indices/pending_scores必须对齐提案时基准，不把accepted历史冒充成员。builder不决定rand1bin/比较平局；原StrictReplacement变体只改原target/trial的select请求，仍用这一结构。codec不能按数值相等重建丢失的token。

**运行入口：** 原正式Project或其run_and_report.py；默认还运行独立SA Case。与本次新增绑定对应的运行/回滚/恢复均未执行。

## binding.decomposition · 同样三个目标，改用MOEA/D方向槽位

**什么时候用：** 将基础三目标Case改用按方向竞争替换，而不是NSGA3末层生态位；DecompositionUnitBuilder只构建weights/neighbors/ideal等结构。

**先准备什么：** adapter.nsga3完整Project配方的另一独立副本；保留ThreeCenters、ClipRepair、薄builder、MemberReport与L0。这里只替换搜索工厂，不保留上一节的ReferencePopulation绑定wrapper。

**放在哪：** 完整替换 `cases/search/adapter/__init__.py`，其余使用基础配方原文件。

**接入步骤：**

```python
from nsgablack.adapters import MOEADAdapter, MOEADConfig
from nsgablack.representation import UniformInitializer, DecompositionUnitBuilder
from nsgablack.units import UnitBinding

def build_adapter():
    return MOEADAdapter(config=MOEADConfig(population_size=12, neighborhood_size=4,
        batch_size=4, decomposition="weighted_sum", variation="de", de_F=.5, de_CR=.9),
        initializer=UniformInitializer(-4., 4.),
        unit_binding=UnitBinding(DecompositionUnitBuilder()))
```

MOEA/D先提供权重/邻域数量，builder按权重距离建立neighbors并初始化ideal为inf；真实反馈来后更新ideal与方向成员仍由Adapter决定。DE变化不要求本例Pipeline有mutator；raw三目标不被weighted_sum覆盖。自动方向投影视图标记本实例created_by，VNS消费须按正式池任务，不解码本Unit。

**怎样判断接对：** 同次members.json有12个二维成员/三列raw反馈；实际algorithm_unit是decomposition schema，weights(12,3)、neighbors(12,4)、ideal(3,)及pending方向状态保持对应。这个切换是算法行为变化，不能继续把报告解释为NSGA3前沿或两个方法的性能比较。

**运行入口：** 原新Project run_project.py与L0；以下变体同时明确改比较方式，不改Problem含义。

### 变体一：方向用Tchebycheff比较

**目的：** 在相同三个原始目标上改方向比较。**改在哪里：** 完整替换工厂：

```python
from nsgablack.adapters import MOEADAdapter, MOEADConfig
from nsgablack.representation import UniformInitializer, DecompositionUnitBuilder
from nsgablack.units import UnitBinding

def build_adapter():
    return MOEADAdapter(config=MOEADConfig(population_size=12, neighborhood_size=4,
        batch_size=4, decomposition="tchebycheff", variation="de", de_F=.5, de_CR=.9),
        initializer=UniformInitializer(-4., 4.),
        unit_binding=UnitBinding(DecompositionUnitBuilder()))
```

**行为变化：** 方向比较改为加权最大偏离ideal，邻域与raw反馈仍保存。**限制：** 不是把Problem换成一个标量，也没有同步变换任何梯度；未验收与旧weighted_sum运行状态的互换。

## binding.archive · 包装器自己的精英历史与内层种群分开

**什么时候用：** 在既有数值种群搜索前，按既有EliteRetention策略从近期已评估记录派生部分提案；ArchiveUnitBuilder拥有wrapper历史条目，不取代内层PopulationUnit。

**先准备什么：** adapter.nsga3完整Project配方的独立副本，原ThreeCenters/12成员与MemberReport；内层NSGA3允许替换普通提案。本节不接到A*这类含边身份且拒绝普通替换的算法。

**放在哪：** 原规范builder保存为base_solver.py，新build_solver.py如下；原adapter工厂保留NSGA3，不装Reference wrapper到顶层。

**接入步骤：**

```python
from nsgablack.adapters import EliteRetentionAdapter, EliteRetentionConfig
from nsgablack.representation import ArchiveUnitBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.set_adapter(EliteRetentionAdapter(solver.adapter,
        EliteRetentionConfig(retention_probability=.5, retention_ratio=.2, history_size=2),
        unit_binding=UnitBinding(ArchiveUnitBuilder())))
    solver.adapter.validate_unit_bindings()
    return solver
```

**怎样判断接对：** MemberReport通过wrapper正式转发仍读取内层准确种群refs；wrapper的get_state另存algorithm_unit.entries，子Adapter作为独立事务参与者保存自己的成员。archive是有限近期反馈记录，内部按原目标和排序，不是新的Pareto精英池或禁忌表。其派生提案仍正式repair/evaluate/admission，不能用历史分数给新孩子免评估。

**运行入口：** 原Project run_project.py。基础双孩子交叉变体可作用于内层，但wrapper派生提案来源须按实际保留的精确ref检查；不得承诺wrapper和单独内层成员相同或搜索更好。静态用法不证明回滚/恢复已验收。

## binding.search_nodes · A*节点与MOA*标签不能共享同一种路径代价布局

**什么时候用：** 要明确路径搜索中SearchNodeBuilder和ParetoLabelBuilder的真实消费者；同一状态由不同父路径到达仍需不同unit_id/parent_id，候选坐标本身不是路径身份。

**先准备什么：** 分别使用《BAYESIAN_AND_GRAPH_SEARCH_APPLICATIONS_CN.md》的adapter.astar与adapter.moa_star完整配方，两个独立catalog_recipes副本，保留各自Problem/邻接/启发式/边代价/Project组与Path/Label报告。原A*是单位边，MOA*是二维边代价，不互用config。

**放在哪：** 每份Case原build_solver.py都保存为同包base_solver.py；A*新规范入口如下。

**接入步骤：**

```python
from nsgablack.representation import SearchNodeBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(SearchNodeBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

MOA*的独立副本采用下面完整入口，不能把单标量g硬塞进Pareto标签：

```python
from nsgablack.representation import ParetoLabelBuilder
from nsgablack.units import UnitBinding
from .base_solver import build_solver as build_base_solver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.adapter.set_unit_binding(UnitBinding(ParetoLabelBuilder()))
    solver.adapter.validate_unit_bindings()
    return solver
```

builder只接收Adapter算出的g/h/f及父引用，不偷偷调用heuristic、edge_cost或Problem。dump/restore保存父关联；MOA*还保留valid及向量代价。SearchNodeBuilder schema与ParetoLabel schema不同，不能以“都含candidate”声明兼容。默认repair_policy=reject保护原边；基础配方障碍邻接/展开顺序变体不需要改变codec。

**怎样判断接对：** A*读原path.json中的found/solution，而非raw目标全0的incumbent；MOA*读原labels结果和二维路径代价，不以Solver标量最佳代替Pareto目标标签。节点状态在frontier/labels集合中逐个dump，不要求存在一个algorithm_unit，也不因读取声明新建根。

**运行入口：** 沿各自原Project组执行，不启动默认composite；两个完整来源均含显式STAGES/GROUPS及L0，新增wrapper不改变组。以下扩展仅改变选用哪份正式算法，不能混合恢复信封。

### 变体一：从单代价路径换成双代价标签

**目的：** 由A*路径目标改为费用/时间两维Pareto路径。**改在哪里：** 新建独立副本，完整应用adapter.moa_star基础配方及上面的ParetoLabelBuilder入口。新入口的导入声明为：

```python
from nsgablack.representation import ParetoLabelBuilder
from nsgablack.units import UnitBinding

def build_label_binding():
    return UnitBinding(ParetoLabelBuilder())
```

此辅助函数仅等价展示上方真实入口已经使用的绑定，不是额外未接上的算法。**行为变化：** 邻接边/启发式/标签比较一起切换到原MOA*配方，完整输入输出维数也变化。**限制：** 不能只换builder；原标量父边状态不能假装已恢复为两维标签。目录按两个完整来源展示，用户每次只保存对应独立Case那一份。

源码：units/contracts.py、structures.py、collections.py；representation/unit_builders.py、structure_builders.py；实际各Adapter的unit_schema/unit_build_operations与get_state/set_state。构建兼容与checkpoint身份是两层检查，声明compatible_schemas不授予旧codec转换权。
