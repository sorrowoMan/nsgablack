# Adapter 的局部算子装配试验

本页保留首轮 NSGA 试验与验证记录。当前已扩展到多族 Adapter，并统一组件状态管理与只读选择请求；逐族支持与四类行为的边界以 [Adapter 行为装配边界](ADAPTER_OPERATION_BOUNDARIES_CN.md) 为准。

本轮先在 NSGA-II、NSGA-III、SPEA2 上提供两个正式装配点：父代选择 `parent_selector` 与候选变化 `mutator`。问题管线不必安装 mutator；初始化、问题修复、候选编解码仍可共用一份 Pipeline。

这验证的是一个具体目标：把“从哪个池取父代”和“怎样变化候选”改成替换局部组件，而不重写算法的 `propose/update`。它没有把全部 Adapter 改成统一的四函数，也没有移除现有 Pipeline 变异入口。

## 最小装配

在标准 Case 的装配函数中，传入独立组件：

```python
from nsgablack.adapters import NSGA2Adapter, MixedPoolParentSelector
from nsgablack.representation import GaussianMutation, RepresentationPipeline

# 问题侧仍可添加 initializer、repair、encoder、decoder。
pipeline = RepresentationPipeline()
adapter = NSGA2Adapter(
    population_size=100,
    offspring_size=100,
    parent_selector=MixedPoolParentSelector("elite", pool_fraction=0.25),
    mutator=GaussianMutation(sigma=0.05),
)
```

`elite` 必须是运行时已存在、已发布且非空的具名子池。它由上游流程或显式池装配创建；选择器不在发现缺池时偷偷新建或改读母池。只有更换来源时，替换 `MixedPoolParentSelector("another_elite", pool_fraction=0.25)` 即可。变异、求值、接纳和环境选择不随之重写。

也可以在运行开始前使用 `adapter.set_parent_selector(...)`、`adapter.set_mutator(...)`。NSGA-III、SPEA2 继承同一入口，各自的环境选择逻辑仍然保留。正式 Case 继续通过已有 `component_overrides={"adapter": adapter}` 装配，不增加第二个构建入口。

## 一轮中发生什么

1. 没有已评估成员时，先走正常初始化、repair、求值与接纳，获得精确成员引用。
2. Adapter 用当前 Unit 的 rank、crowding 和有序 SolutionRef 构建只读 `ParentSelectionRequest`。
3. 选择器一次返回 `2 * offspring_size` 个父代引用。混合选择器按指定比例从具名子池均匀抽样，其余位置按当前种群的 rank/crowding 锦标赛选择；允许有放回抽样。
4. 控制面按精确引用读取候选，Adapter 在副本上交叉，再调用独立 mutator。
5. 新提案获得新身份；双方父代精确引用记录在 `parent_solution_refs` 因果 metadata 中。父候选不被原位改写。
6. 预算裁剪、ProblemRepair、Unit 对账、Problem/Provider 求值、Bias、BatchDisposition 与 Unit 成员维护沿用既有流程。

混合比例是整批父代配额，按最接近的整数取整后打散位置；它不保证每一对父代都来自不同来源。读取外部父代不等于把它直接装入当前 Unit；后代仍须重新送评并参加本算法环境选择。

## 两个组件各自看见什么

父代选择器实现 `select(request, *, pool, rng)`。请求包含有序成员引用、脱离且只读的 rank/crowding、数量和调用局部标量 context。它不接收可写 Unit 或 Solver 私有字段。池引用必须在当前 scope 可读，返回数量与类型须严格匹配。

mutator 实现 `mutate(candidate, context)`，也可省略 context。需要 Unit 时，声明 `UnitInputSpec` 并实现 `mutate(candidate, context, *, unit)`；Adapter 从自己的 Unit 捕获只读输入。独立绑定与 Pipeline 绑定使用同一输入检查，不能从共享 context 猜测算法所有者。

直接 mutator 与非空 `set_mutation_operator(name)` 互斥，避免同一调用存在两种选择。没有直接绑定时，旧的具名／默认 Pipeline 变异路径保持有效。

## 状态与失败

每个直接组件须提供 `checkpoint_identity() -> Mapping`，声明决定其行为的配置。无持久状态的组件显式声明 `stateless=True`；有状态组件提供 `get_state()/set_state()`，状态为可脱离的数据 Mapping。框架不会扫描或复制组件的 `__dict__`、锁、executor 或 Provider session。

绑定随所属 Adapter 的正式 codec 进入步骤快照和 checkpoint。恢复要求组件身份与配置匹配；不允许用少一个组件或不同参数的装配读取绑定状态。GaussianMutation 显式保存 RNG 状态和配置。组件可用 `set_random_seed` 接收运行种子；没有这个方法时不猜其随机源。

同一有状态组件对象不能由多个绑定重复拥有。需要独立状态时显式创建实例；声明 stateless 是组件作者的契约，不能由 Doctor 证明不存在隐藏副作用。透明包装也不能再次登记子 Adapter 已拥有的绑定。

异常失败按既有步骤事务恢复绑定状态。正常零接纳依旧遵循现有 propose/disposition 语义，不承诺撤销整个采样过程。`parent_solution_refs` 只是因果记录，不隐式扩展池的保留根；历史可读性继续服从子池成员关系、显式 retain 和既有保留窗口。

## 边界与后续

本轮接入的是父代来源和候选变化；交叉仍走现有入口，初始化与修复尚未全面拆出 Pipeline。其他 Adapter 的直接组件所有权需要分别接入其状态 codec，不能因为底层存在执行入口就声称已支持全部算法。

运行装配记录的 `operator_bindings` 保存组件引用与配置身份，不保存 RNG 状态，并进入装配指纹。当前 BlackBase 通用 `--check` 的顶层 `mutator` 字段仍只表示 Pipeline 槽位，尚不展示直接绑定组件；不能据此断言 Adapter 没有变异。真实绑定可通过 Adapter 的 `get_local_operator_bindings()` 与运行装配记录核对。

单独绑定的搜索组件属于 nsgablack。问题评估含义由 Problem 定义；运行事务和 Project 编排继续由共享底座提供。要扩大拆解范围，应逐项验证真实消费者、依赖输入、状态恢复和修改成本，避免增加一层只有名字的容器。

## 2026-10-19 验证记录

环境为 Windows、Python 3.13.2、pytest 8.3.5。最终代码覆盖 276 项用例，按整批与失败项复测对账：整批 275 项通过，新增脚手架测试将空列表断言修正为实际的空元组后，单独 1 项通过；不是一次整批全绿输出。

```powershell
python -m pytest tests/test_direct_mutation_binding.py tests/test_pool_parent_selection.py tests/test_operator_binding_contracts.py tests/test_runtime_surface_tracker.py tests/test_operator_scaffold_integration.py tests/test_unit_operator_inputs.py tests/test_shared_mutation_pipeline.py tests/test_adapter_step_transactions.py tests/test_checkpoint_resume_plugin.py tests/test_proposal_repair.py tests/test_population_member_operations.py tests/test_runtime_contract_refinement.py tests/test_scaffold_component_provider.py tests/test_project_scaffold_check_output.py tests/test_catalog_context_contracts.py tests/test_vns_adapter_warnings.py tests/test_cdm_psl_decomposition.py -q
python -m pytest tests/test_operator_scaffold_integration.py -q --tb=short
```

覆盖范围包括：独立变异签名与只读 Unit 输入，精确父代版本与换池来源，父候选不被修改，语义 metadata 保留，修复与部分接纳，异常后随机状态恢复，正式 checkpoint，错装配与重复状态归属拒绝，以及运行装配指纹。未绑定路径继续接受既有 Pipeline；合法裸 Pipeline 的 mutate 能力仍能被识别。

实际生成的 Project/Case 通过正式 build_case、ResourceAllocator lease 和 run_case 路径执行两步；Pipeline 只保留初始化与修复，绑定 GaussianMutation 确实改变了候选。Doctor 的 build 检查和运行前后契约检查通过，mutator 的状态只归 Adapter codec 所有。它没有使用绕过标准脚手架的私有运行器。

Catalog 的 `tool.mixed_pool_parent_selector` 已分别在 `default` 与 `framework-core` 口径通过 CLI 查得，装配说明、参数和依赖可见。这里验证可发现性，不把 Catalog 的签名检查算作算法行为证明。

仓库级严格 Doctor 最终通过：**0 error、0 warning、175 info；463 个检查项 completed、90 个 skipped**。

```powershell
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json
```

该命令没有启用 `--build`，跳过项包括 Case 构建；不能把它们算作已运行。上面生成的独立 Case 另行执行了 `instantiate_solver=True` 的正式 Doctor 构建检查及真实求解。首次仓库检查发现 GaussianMutation 缺少恢复级别声明，补齐 L1 后完成最终复核。

既有 SA 混合管线测试同步纠正了基准语义：初始未评分点先 repair/送评为 18，下一轮才变异至 17 并 repair 为 27。没有为让旧断言通过而修改 SA 算法。整批另有一条已有 MOEA/D 未配置 ParetoArchivePlugin 的提示性 warning。

没有运行真实 CDM-PSL 模型、性能 benchmark 或仓库完整测试集；本轮不证明任意算子无副作用或任意算法均可如此拆解。


## 父代成员属性交接（2026-11-12）

NSGA-II/III、SPEA2 的父代选择请求提供 request.members Pool，允许返回其筛选/有放回抽样结果。完整 change 通过 request.parent_pool.member_field 读取精确槽位属性；父代下标记录在 parent_member_indices。旧唯一引用仍可返回，重复引用的槽位歧义在送评前拒绝；外部父代字段需要显式 default。完整装配、MixedPoolParentSelector 边界与默认数值变异路径限制见 [Pool 接口手册](POOL_API_REFERENCE_CN.md)。
