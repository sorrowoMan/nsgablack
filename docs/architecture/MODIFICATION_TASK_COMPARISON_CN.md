# 算法修改任务对照：nsgablack 与 pymoo 0.6.2

## 研究问题与首轮范围

本实验不预设 nsgablack 更好。目标是区分：修改是否局部化、维护工作是否只是搬家，以及接口声明和运行成本。代码位于 `benchmarks/modification_tasks.py`，通过已有 algorithm_transparency Project 的 matrix Case 执行，复用 Project L0、取消检查与 Artifact 发布。

这是首轮可运行的扩展面实验，不是论文最终基准。前两项控制相同候选流并调用真实环境更新组件；第三项使用双方原生精修算法完成换装，但不是同算法、同预算的效果实验。不能把它们混成“框架综合领先”的分数。

## 任务一：只记录成员年龄

定义：新成员为 0；老成员经过一次环境选择且存活则增加 1。候选数值不能代替身份；年龄属于成员，不是全局 generation。固定四个初始成员，连续六批四个新候选，两个目标严格同序，避免 crowding 并列带来的算法差异。

nsgablack 的扩展是 AgeUnit、member_fields、schema、on_members_changed 和 AgeBuilder，通过 UnitBinding 装配。真实 NSGA2Adapter.update 负责选择和成员发布，不认识 age。

pymoo 的扩展是 Individual 自定义 age/established/identity 属性以及 AgeSurvival。默认选择调用原 RankAndCrowding，选中后增加老成员年龄。无需修改 pymoo 源码，也无需新建候选结构类。

结果：双方每轮成员身份与年龄一致，初始四个成员最后年龄为 6。这个例子没有证明 nsgablack 更省代码：两边都局部化，pymoo 的动态属性更轻；nsgablack 为字段维护和发布提供更多声明及校验。

## 任务二：让年龄参与选择

明确改变算法：年龄小于 2 的候选优先；组内按第一个目标排序，不足四个则用老成员补足。该政策不是标准 NSGA-II，也不是声称其优化效果更好。

双方共享 age_order 作为任务规格的可执行实现，排除排序政策本身的差异。共同代码不能被算作某一方独有的实现优势。

nsgablack 使用 AgeSelectingNSGA 扩展 `_select_survivors`，从当前 Unit 获取旧成员年龄，新候选年龄为 0。这是旧版数组级实验选择的路径，不是框架必须如此；真实 Pool＋Unit 复验已证明无需覆盖 Adapter，见下方修正。

pymoo 在同一个 AgeSurvival 中切换选择政策，仍维护 Individual 年龄。状态维护与决策集中在 Survival，代码更紧凑，但复用到别的维护场景时需要重新审查其生命周期。

结果：双方七轮轨迹一致。独立测试断言第三次环境选择后，旧的优质成员被新成员替代，年龄重置为 0；同时验证年轻成员不足时补足规则。这证明政策确实改变决策，不只是在记录字段。

## 任务三：替换精修器

nsgablack：MOEA/D 发布两个投影视图，固定 PoolTaskSpec 和 Router，精修器由 PatternSearchAdapter 换为 SimulatedAnnealingAdapter。两次均完成任务，实际求值各 12 次。原先假设固定四个 Solver.step 就完成任务导致首轮失败；改为读取正式 task_status，并设置最多 20 次尝试保护。失败收据保留。

pymoo：固定两个方向 [0,1]、[1,0] 和起点 3，将原始双目标 [x²,(x-6)²] 包成冻结加权和 Problem；保持 next/result 调用方式，将 PatternSearch 换为 NelderMead，两次均完成，实际求值各 62 次（原生终止条件允许批次越过 30 次/方向阈值）。使用成熟算法原生扩展面，不故意重写冗长调度器。

这项只能支持“双方换装都可以很局部”的结论。nsgablack 额外演示了投影池任务，pymoo 通过两个投影 Problem 完成相同来源的双方向精修，核对结果候选的原始反馈；双方均未在本实验实现嵌套或返回原算法竞争；原生替代算法也不相同。因此不能比较收敛、速度或宣称对方缺乏投影能力。严格同算法、同预算及相同失败模型的对照仍需后续完成。

## 必须计入的修改与学习内容

- nsgablack 状态扩展：Unit 字段、成员变化映射、schema、builder、binding；年龄参与选择额外需要了解 Adapter 覆盖点。
- pymoo 状态扩展：Individual 属性、Population 合并、Survival 调用时点；年龄参与选择复用同一个 Survival。
- nsgablack 精修装配：RoleSpec、PoolTaskSpec、视图来源、任务完成状态、局部算法参数。
- pymoo 精修装配：Algorithm 构造、Problem、起点、终止条件、结果读取。

这些是阅读负担清单，不是学习时间测量。代码行数受格式和共享帮助函数影响，不作为易用性的替代指标。正式学习成本需要让参与者在相同任务说明下实现，记录时间、求助次数、错误与正确完成率，并控制其框架熟悉程度。

## 执行与测量

```powershell
.benchmark-venv/Scripts/python.exe examples/cases/algorithm_transparency/run_project.py --group modifications --run-id my_modifications
.benchmark-venv/Scripts/python.exe -m pytest tests/test_modification_tasks.py -q
```

实测成功收据：`examples/cases/algorithm_transparency/.blackbase/runs/modifications_20261112_v3/manifest.json`。失败初版为 `modifications_20261112`，不覆盖。

年龄任务各执行七次，第一遍预热，六次记录中位数。一次样本含构造及七批更新，不含求值、完整 Solver 生命周期或恢复：

- 仅年龄：nsgablack 约 9.47 ms；pymoo 约 1.04 ms。
- 年龄选择：nsgablack 约 5.97 ms；pymoo 约 0.66 ms。

nsgablack Adapter.update 还维护 token、结构校验、反馈状态等，而 pymoo 此处测 Survival；因此这是实现此受控任务的局部路径成本，不是同层原语比较，更不是全框架倍率。该结果不支持性能优势。当前没有单独剥离字段更新、校验与 codec 的耗时，也未作多进程重复、RSS 或人类学习实验。

## 可以与不能主张的结论

可以：成员状态维护可以独立于搜索决策；同一成员变化协议在本例中正确维护了年龄；池任务容许支持该契约的原生精修器换装。

不能：年龄机制是独有创新；比 pymoo 更易修改；更低运行开销；任意算法直接互换；或已证明论文创新性。

这轮最重要的发现是：简单扩展已有框架也很好做。后续若要证明 Unit 的价值，应增加成员重排、局部重复槽位替换、部分接纳及恢复等任务，检查同一维护规则是否仍可复用，同时给 pymoo 提供合理的封装机会，而不是仅对比临时脚本。

机器可读报告为 `results/modification_task_report.json`，含逐轮轨迹、六次耗时样本、实际求值、输出、源码 SHA 和按符号的物理行数清单。行数同时包含共享基建和实验帮助函数，不能直接解释成用户净改动量。3 项独立行为测试通过。Project Doctor/build 为 0 error、10 warning、19 info；警告是五个原有 Case 的管线入口建议与未收集到 context contracts，不把 strict 返回非零隐藏为通过。


## Pool＋Unit 复验：修正首次解释

用户指出首次微实验绕过了真实池入口。新增 pool_native_age 使用原 NSGA2Adapter、真实 ComposableSolver、Problem 求值及 SolutionPool，选择器通过 set_selector 装配；未改核心，也没有 Adapter 子类。

BoundAgePoolSelector 只绑定所属 Adapter 和 Solver，不拥有第二份年龄状态。每次选择读取 Unit 的年龄及公开 get_population_solution_refs，冻结为本次调用参数。choose_age_pool 用精确 SolutionRef 将候选映射到成员年龄，未知新版本按新成员年龄 0 处理，调用 Pool.chosen/Pool.take 返回所选子集；框架按原 offered 坐标交付 Unit 更新。

当前示例显式要求种群成员引用唯一，不将其推广到同一引用占多个槽位且槽位年龄不同的情形。读取的是 algorithm_unit 上的当前成员字段，由本次选择调用同步消费；不是预先创建全局年龄池。首次尚无已评估成员时，不读取不存在的正式成员引用。

真实路径分别跑仅年龄、年龄选择两组，每组七批、28 次正式求值；逐轮成员标签和年龄与 pymoo 一致。标签 cN 只用于跨框架对照，选择内部不按数值或标签匹配，而是按真实 SolutionRef。成功收据为 modifications_pool_20261112_v3；失败的两个装配尝试保留。第一次暴露了默认数值初始化会先形成未评估种群，第二次调整中明确区分了 initializer 与 mutator 的状态归属，最终使用独立的可恢复固定输入组件。

因此撤回“因为 SelectionRequest 没有 age，所以必须覆盖 Adapter”的解释。准确结论是：现有公开选择装配配合 Pool 与 Unit，足以表达本例。仍有一段必要的所有者绑定和引用连接代码；不能据此宣称年龄会自动出现在 Pool 中，或比 pymoo 更少代码。

旧局部路径耗时不适用于这条完整 Solver 路径，本轮未用它与 pymoo Survival 的局部耗时比较。恢复能力也未因组件声明可恢复而直接认定通过；本例尚未做完整 checkpoint 故障实验。

## 复杂场景复验（2026-11-12）

成功 Project 收据 `modifications_complex_20261112_v4`；汇总 `results/modification_complex_report.json`。8 项独立测试通过，初始失败收据保留。框架核心未改，仍使用同一个 AgeUnit.on_members_changed。

### 重排

选择后将所选 Pool 顺序反转，pymoo 同样反转所选 Population。七轮身份和年龄一致。Pool 的原始出现坐标用于回传选择，Unit 按 previous_member_indices 更新年龄；没有新增“反转时怎么修年龄”的维护分支。

### 部分接纳

首批四个初始化候选全部接纳；后续每批四个候选均送评，但只接纳原始下标 1、3。nsgablack 通过 BatchDisposition，pymoo 参考侧显式筛选对应输入再调用 Survival。最终种群与年龄逐轮一致，并断言拒绝的候选未混入成员。nsgablack 的实际求值计数仍为 28，不把拒绝当作未求值。pymoo 这条路径是预计算反馈参考，不把其局部更新时间和完整 Solver 时间相除。

### 重排＋部分接纳＋恢复

前三批提交后，通过 CheckpointResumePlugin 构造正式 payload，pickle 往返使其脱离旧对象，再创建新 Solver、重新绑定选择器所属 Adapter，排队应用恢复信封，继续剩余批次。结果与不中断运行及 pymoo 参考逐轮一致。pymoo 保存恢复的是本受控任务必要的 Population（含年龄），不是声称已验证任意完整 pymoo Algorithm 的恢复。

本例没有让年龄钩子在恢复时重新计算年龄，也没有在选择器中存储第二份年龄。恢复的所有者绑定重建来自装配；绑定对象不是持久化的活 Solver。这里使用了 checkpoint 插件的 payload 辅助接口，不是公开 CLI 文件恢复，也未模拟进程强杀、外部求值副作用或数据库恢复。

### 重复槽位

建立真实池引用集合 `[a,a,b]`，前两个槽位引用同一候选版本，但 Unit 年龄分别为 1、5，第三个为 2。选择并反转得到槽位 `[1,0]`。提交后身份为 `[a,a]`，年龄分别为 `[6,2]`；两个相同引用没有被合并。

原来的引用字典 helper 明确拒绝重复成员。因此这部分不能原样复用；本例在选择前取得与 offered Pool 原始位置一致的年龄，再通过 Pool.take 保留出现坐标。Unit 的维护钩子本身无需改变。这个实验走真实池视图与 Unit 发布，但不是一轮完整 MOEA/D 更新。

pymoo 使用两个独立 Individual 槽位对象携带同一个候选身份，也得到 `[6,2]`。不能把两个槽位复用同一个可写 Individual 所导致的别名问题当作 pymoo 必然缺陷；合理封装后同样能正确表达。

### 所有者绑定与引用对齐究竟是什么

所有者绑定：告诉选择器读哪一个 Adapter 的 Unit。两个种群都含 a，不代表 a 的成员年龄相同。示例通过 BoundAgePoolSelector(adapter,solver) 显式绑定，选择器声明不拥有可变算法状态。

引用对齐：把“本次 offered Pool 的每一行”对应到“该 Unit 的哪个成员”，新接纳成员年龄为 0。唯一引用时可以用字典；重复引用时必须额外保留槽位/出现位置。只给池起名，不能自动推导这种关系。

当前可支持的优势主张是：重排、部分接纳、恢复和重复槽位的成员更新复用了同一维护规则。尚不能主张整体代码更少、学习更快或运行更快；重复槽位的连接规则仍需显式描述，完整故障语义也需要双方对等的实验。


## 成员字段读取收敛（2026-11-12，替代上文旧绑定示例）

核对确认旧 BoundAgePoolSelector 写复杂了：Pool 已维护出现位置，示例另建引用字典反而丢失重复槽位含义。
已删除绑定类；保留 choose_age_pool 仅作旧引用字典歧义的负例，不再用于真实选择。
新增通用 Pool.member_field(name, default=...)，NSGA 家族入口一次提供所属 Unit 与槽位关系。
选择函数 select_age_members 为 3 个非空物理行（含 def）：读取 age、调用共享 age_order、可选反转。
装配仍使用 set_selector(partial(...))；不再捕获 Solver/Adapter，不需要自定义 checkpoint_identity。

除选择规则和双方共有的输入准备，当前年龄例子的用户级额外对齐代码为 0 行。
AgeUnit/AgeBuilder 的字段声明、年龄更新规则仍保留；这些包含实际新增状态语义，不能全算成框架连接成本。
pymoo 仍直接通过 pop.get("age") 读取属性，用户级对齐代码同为 0 行。
双方都复用既有状态保存机制，字段没有新增独立恢复 codec；整个 Solver 与 Population 的恢复脚本范围仍不对等，不比较这部分行数。

新增框架代码不是免费：包括调用期字段冻结、槽位映射、只读读取及 chosen/partition 的坐标传递。
这是共享实现成本，不能隐藏，也不能按每个字段重复计入用户改动。尚未测量该读取扩展的独立性能成本。
真实 Project 收据 modifications_member_fields_20261112 验证年龄、重排、部分接纳、恢复与重复槽位对照。
这支持“无需逐字段连接代码”，不支持“全面优于 pymoo”或“所有 Adapter 均已接入”。
