# 池输入与普通函数算法试作：VNS / MOEA-D

2026-10-20 后续落地：正式 Project 已增加 GA Case，并将三个 Case 的精英维护移到本批反馈之后。
GA 演示一次 change 交回两个后代与普通 choose(Pool)->Pool；旧两例保留算法自身语义。
最新可运行代码、真实结果与恢复验证以 [Project README](../../examples/cases/pool_workflow_pilot/README.md)
及 [接口手册第 10–11 节](POOL_API_REFERENCE_CN.md) 为准。下面保留首轮试作范围与历史差距。

后续实现已扩展为[池驱动变化编排](POOL_CHANGE_ORCHESTRATION_CN.md)：普通函数可以额外取解，
显式声明接纳后输出；下面第 8 节保留首轮差距记录，不代表这些接缝仍全部缺失。

日期：2026-10-20。可运行 Project 见
[`examples/cases/pool_workflow_pilot`](../../examples/cases/pool_workflow_pilot/README.md)。

## 1. 本轮范围

用户在 Project 中写普通函数，把输入候选变成新候选；框架负责来源身份、
问题修复、正式求值、接纳、Unit 更新与事务。函数可以先交叉再变异，
也可以先分别变异再交叉，不要求继承变异基类或手写 checkpoint 方法。

这次用现有 Pool 接口试作 VNS 与 MOEA/D，保留原生算法比较和状态推进。
没有修改 `core/state/solution_pool.py`，没有增加第二套 Solver、评估或资源循环。
实际调用主干已拆出 `initiate`、`chose`、`change`、`return_feedback`；
普通 `change=` 函数真实参与送评候选生成，不是只给原 Adapter 重新命名。

这些方法仍由算法组织，**尚未开放任意阶段脚本、任意多输出或通用池 DSL**。
本轮先验证实际算法和普通函数能否自然配合，再据此改 Pool。

## 2. 最小用户代码

```python
def neighborhood_change(request, *, rng):
    x = request.candidate
    sigma = request.parameters["sigma"]
    shifted = x + rng.normal(0, sigma, x.shape)
    return 0.95 * shifted

vns = VNSAdapter(change=neighborhood_change)
```

```python
def cross_then_mutate(request, *, rng):
    a, b = request.parents[:2]
    child = 0.5 * (a + b)
    return child + rng.normal(0, 0.05, child.shape)

def mutate_then_cross(request, *, rng):
    a, b = request.parents[:2]
    a1 = a + rng.normal(0, 0.05, a.shape)
    b1 = b + rng.normal(0, 0.05, b.shape)
    return 0.5 * (a1 + b1)

moead = MOEADAdapter(change=cross_then_mutate)
```

这是装配片段，不是完整入口。Problem、Pipeline、种子源和资源由标准 Case 组装。
更换顺序只换 Project 函数或绑定，不修改框架源码。
高斯例子的两个顺序可能具有相同的部分统计性质，不能凭顺序宣称质量不同；
测试另用非线性变换确认数据连接确实不同。本例不作性能比较。

## 3. ChangeRequest

函数签名为 `function(request, *, rng) -> 单个候选`。

- `parents`：脱离原 Unit 的只读二维数值矩阵。
- `candidate`：`parents[0]`，本次变化的锚点。
- `source_refs`：与输入行对齐的精确候选版本；低层无身份调用可为空。
- `parameters`：算法明确提供的只读数据，不通过可写 Solver 猜状态。
- `context`：一次调用的标量上下文投影，不提供共享存储、服务或大数组。
- `unit_id`：当前拥有者的算法结构身份。
- `rng`：所属 Adapter 的随机数发生器，随已有事务和 checkpoint 保存。

父集允许数值相同的不同身份，也允许相同引用占据不同槽位。
输入按成员位置构建，不按数值去重。需要改数组时先 `copy()`。

本轮每次函数返回一个候选。VNS 按 batch_size 重复调用；MOEA/D 每个被选方向调用一次。
没有同时引入任意批次输出到方向索引的新映射协议。

source_refs 是声明的可用输入来源，不证明函数实际读取每一行。
provenance 的 `change_input_refs` 记录该输入集，不冒充实际交叉父代。
它不自动形成无限历史保留，历史可读窗口仍服从 Pool retention。

## 4. VNS 主干

1. **Initiate**：显式池输入优先，按需建立 CandidateUnit、NeighborhoodUnit；
   无池输入时仍可使用原 initializer。先正常求值起点，不向后代借分。
2. **Change**：从当前点生成邻域；参数提供 k、sigma。
   函数可组合多个计算操作；未绑定时保留原 Pipeline/mutator 行为。
3. **Chose**：反馈返回后，从本次实际接纳候选中提名结果。
   投影任务保留冻结比较框架与可行性顺序，不改写母池 raw feedback。
4. **Return**：按原改善条件更新当前 Unit 和精确引用；改善时重置邻域，
   未改善时推进邻域或按原策略重启。函数不偷偷改 k 或 current_score。

此处 Chose 是现有反馈侧选择，不表示所有阶段都已成为任意池脚本。
预算裁剪、repair 对账、求值、部分接纳与提交仍由原控制面执行。

## 5. MOEA/D 主干

1. **Initiate**：读取声明的母池输入，完成正式 bootstrap 后建立方向 Unit。
   未完成时不向下游发布半个方向集合。
2. **Chose**：选择子问题及邻域/全局父集，保留 pending slot/mode 对齐。
3. **Change**：函数替换完整变化，不是在原 DE 之后追加扰动。
   parents[0] 是目标槽位，其后是按槽位去重的邻域/全局候选；引用同序。
   参数包括方向、权重、ideal、邻域与 parent_indices 等必要数据。
4. **Return**：正式反馈返回后按当前分解规则更新 ideal、竞争槽位，
   保留 nr、可行性、扩展成员字段、token 与精确池版本。

方向子池沿用原算法发布。普通函数不取得发布权，不把方向标量写回 raw objectives。

## 6. 普通函数的状态和恢复

用户不用写包装。内部桥接到 OperatorBinding，自动记录主函数代码、不可变
闭包/default/partial 参数，以及直接同模块 helper 的代码身份。
恢复时绑定不符明确失败，不重跑函数来恢复状态。

函数按契约是无隐藏持久状态的计算：随机性用传入 rng，配置用请求或不可变参数。
可变闭包、锁、executor、Provider session 不能作为捕获配置。
确有可恢复内部状态的操作继续使用原显式状态组件。

指纹不是整个 Python 依赖图签名，也不是副作用沙箱。
外部库、更深 helper 和任意模块副作用属于代码/环境契约，不能自动证明纯度或数学性质。

完整 change 与直属 mutator、具名 Pipeline mutation 互斥，避免生成路径静默叠加。
共享 Pipeline 的默认 mutator 可以存在；实际绑定完整 change 的叶不执行它。

## 7. 母池先有候选，算法再建立 Unit

Project 使用正式 on_solver_init 启动钩子调用公开 solver.init_population，
从 Pipeline initializer 生成候选并登记母池，不建立全局种群、不提前求值。
后续 PoolTaskSpec(mode="initialize") 选择输入，算法首次实际运行才建立 Unit。

启动桥必须观察恢复后的状态，不重播已经完成的种子生成。
它只连接生命周期，不做算法选择。当前仍需要这段桥接代码，正是下一轮 source 面的缺口。

## 8. 下一轮 Pool 改造的输入

以下保留首轮需求，并标明后续完成程度：

- **源入口**：Pipeline 向母池提供初始/补充候选成为明确装配动作，减少启动桥。
- **选择与视图**：只读 main/subpool/read 与 take/random/merge 已接通；通用 map/beunit 仍未提供。
- **Unit 绑定**：选定集合到 Unit 的写法更直接，池不成为算法结构所有者。
- **集合更新**：普通子池提供清楚的成员替换/裁剪，保持 view_id/revision；
  不通过删除重建维护精英池，不误删其他 Unit 仍引用的候选。
- **结果去向**：ChangeResult/PoolOutput 已能指定普通子池的接纳后输出；Unit 最终选择仍由所属算法负责。
- **可见性**：来源冻结到已提交时点，命名输出随同一事务发布；不得读取半提交集合。

验收重点是同一普通函数能否在不同来源、去向与调用阶段复用。

## 9. 验证范围

新测试：tests/test_plain_change_contracts.py、test_vns_plain_change.py、
test_moead_plain_change.py，覆盖只读输入、多操作顺序、基准先评、来源身份、
非前缀接纳、失败恢复 RNG/Unit、投影及 checkpoint。

Project 实际计数、种子/Unit 时序、方向引用和 raw feedback 核对见其 README 与结果。
测试组可能重叠，不累计不同批次的通过数；示例也不证明性能优越性。

2026-10-20 同批综合回归：**371 passed**，覆盖 21 个测试模块，耗时 161.63 秒。
范围包括三份新增 change 测试、原 VNS/MOEA-D、绑定审查、种群/轨迹装配、惰性 Unit、
repair、事务、池成员、投影/嵌套精修、共享 Pipeline、Unit 输入、Catalog 与生成脚手架。
59 条 warning 为测试未装配可选 ParetoArchive 或未声明邻域上下文的既有提示；不是断言失败。
这不是全仓库测试结果，也不把之前重叠的专项次数累计进去。

另外运行 `tests/test_pool_workflow_pilot_resume.py`：**2 passed**，耗时 9.17 秒。
两项均通过标准 Case builder 和 Project L0 授权运行：原运行提交 6 步，
新实例从第 3 次提交后的正式 checkpoint 恢复到第 6 步。
恢复实例的 initializer 被替换为报错函数，仍可完成续跑；后续求值候选、最终原始反馈、
候选引用、Unit 身份与算法状态均与原运行对齐，确认没有重播母池种子生成。
这两项是单独的恢复实验，不代表下面保存的 10 步示例曾中断恢复。

标准 Project 的 `--strict --build --catalog-audit` 在 default / framework-core 均为
0 errors、0 warnings、17 infos，26 项检查全部 completed。
仓库根静态检查为 0 errors、0 warnings、194 infos，517 completed、97 skipped；
根命令未启用 --build，不能用它声称所有 Case 已经装配/执行。
