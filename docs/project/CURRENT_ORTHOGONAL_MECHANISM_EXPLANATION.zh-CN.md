# 当前正交符号机制说明

这份文档先把当前系统里的真实机制固定下来，方便后面逐条追问、修正和继续设计。

当前这套机制最准确的理解是：

`原始特征 -> basis_set head -> basis object 空间 -> expression head -> 多次运行 consensus -> locked-core refinement`

它已经不是“单次普通符号回归”了，而是一套嵌套式、分层式的符号搜索系统。你前面说的“其实第一个过程只是换了 head，本质上还是符号回归”，这个判断现在是对的，而且代码里已经基本按这个思路落下来了。

## 1. 它现在本质上是什么

1. 它不是直接拿原始特征去搜最终表达式。
2. 它先做一次“结构发现”，产出一组相对正交、相对互补的 `basis`。
3. 然后再把这些 `basis` 当成新的“对象空间”，做一次小预算的符号回归。
4. 如果挂到 `nsgablack` 外层，还会把这个过程重复跑很多次，做 `consensus` 和 `locked-core`。

更贴近前面的语言，就是：

1. 第一阶段是 `basis_set head`
2. 第二阶段是 `expression head`
3. 两阶段读的是同一份数据
4. 只是目标函数、搜索空间、输出 head 不一样

## 2. 单次 run 里，真实是怎么搜的

一条 `mlblack` 的 orthogonal run，大致是这 8 步。

### 2.1 先建候选池

- 从原始特征出发，用标准候选池生成器建一批符号候选。
- 如果配置了 gate/piecewise 提示，还会先注入条件 primitive，比如 `gate_step`、`piecewise_hinge`、`piecewise`。
- 所以外层不是从零空手造式子，而是“标准候选池 + 条件增强 + 后续局部 reopen”。

### 2.2 第一层筛选 `screen`

这一层更准确的理解，不应该是“给所有候选项打一个边际分数然后排序”，而应该是：

`先判断哪些候选在信息上其实是同一簇，再让每个信息簇只保留少数正式代表进入后续竞争。`

也就是说，第一层 `screen` 的核心职责，不是简单挑“最像目标的项”，而是做两件事：

1. 识别候选是否提供了新的、相对正交的信息
2. 防止一组局部近似等价的候选并排活下来，抢占 basis 名额

当前更准确的口径可以写成：

- `target corr`：候选和目标的边际相关性
- `residual gain`：候选单独对当前目标的解释增益
- `semantic novelty`：候选在语义家族上是不是老在重复
- `consensus prior`：候选所在的机制簇，是否和此前多次运行中稳定出现过的 core 簇接近
- `mechanistic prior`：它是否更像预先提示的机制组合
- `periodic prior`：它是否更像真实周期 family，而不是局部平滑替代
- `complexity penalty`：复杂度惩罚

但是，真正重要的认识升级是：

`consensus prior` 不能被理解成“哪个具体 term 更像历史熟脸，哪个就该优先活下来”。  
更合理的用法是“历史上哪个信息簇/机制簇更稳定，因此这个簇值得保留一个代表继续竞争”。`

这背后的原因是：

1. 一组候选如果表达的是近似同一条信息轴，那么很多时候本来就应该只允许 1 个正式存活
2. 否则谁先出现、谁更容易被生成、谁先吃到 prior 加分，就会带来明显偏置
3. 这种偏置在多次运行后还会被 `consensus prior` 反过来放大

典型例子是：

- 真机制可能是 `x1 * x2`
- 但在当前区间里，`x1 * tanh(x2)`、`x1 * ln(1+x2)` 之类的变形项也可能和它非常接近
- 如果系统只按 term 边际分数排队，就很容易让局部替代项先抢位
- 一旦它先活下来，真正的机制项后续的新增残差信息就会变小，进一步被压制

所以第一层 `screen` 现在更应该被理解成：

`信息簇去重 + 新信息准入`

而不是：

`候选项分数排行榜`

更严格地说，一个候选想在第一层活下来，理想上应该回答三个问题：

1. 它是否代表了一个值得继续保留的信息簇
2. 在这个簇内部，它是否比其它近似表达更像一个好的机制代表
3. 它是否对当前系统尚未解释的部分，提供了新的、相对正交的信息

因此，后续改进方向也很明确：

1. 第一层先做信息相似簇压缩，而不是允许大量近似等价项并排进入
2. `consensus prior` 从“term 级强加分”降成“簇级保留偏置”
3. 更理想的新信息判断，应该逐步往 OMP 式投影残差准则推进

但这里还要再往前收紧一步：

`第一层真正应该坍缩的，不只是“高相关候选”，而是“统一信息源对象”。`

但这里还有一个非常关键的边界要说清：

`不是所有“带变换”的式子都应该坍缩。`

更准确的规则应该是：

`只坍缩“包裹整个对象的外层变换”，不坍缩“嵌在对象内部结构里的变换”。`

也就是说，外层如果真的是在找 basis，那么它不应该把下面这些东西当成多个 basis 名额：

- `A`、`A^2`、`tanh(A)`
- `A/B`、`sin(A/B)`、`tanh(A/B)`
- `exp(-Ea/T)` 和它内部真正承载机制关系的 `Ea/T`

更合理的理解是：

1. `A` 是一个信息源对象
2. `A/B` 是另一个信息源对象
3. `sin(A/B)` 不是新对象，而是对 `A/B` 这个对象的一次变换
4. `A^2` 也不是新对象，而是对 `A` 这个对象的一次变换

但下面这种情况不能简单坍缩：

- `x1*x2*x3`
- `x1*sin(x2)*x3`

这两个虽然共享了一部分来源特征，但它们不是同一个对象。  
原因不是“写法不同”，而是：

`sin(x2)` 被放在了对象内部，参与了结构组合本身。`

这意味着它改变的已经不是“对象外面再包什么 head”，而是对象本体的内部机制结构。

所以外层 basis discovery 更准确的职责，不是“选一堆 term”，而是：

`在候选表达式里识别真正的信息源对象，然后每个对象只允许保留一个正式 basis 身份。`

这背后的理由非常直接：

1. 外层找 basis 的目的，是找信息边界，而不是提前把最终表达式写死
2. 第二阶段本来就是 `basis-conditioned symbolic regression`
3. 但第二阶段并不垄断所有变换表达
4. 第一阶段一样可以发现带结构意义的变换对象
5. 真正要后移到第二阶段优先决定的，是“包裹整个对象的外层 realization head”

换句话说：

- 第一阶段解决“该保留哪个对象”
- 第二阶段重点解决“这个对象最后以什么外层 realization 写出来”
- 但如果变换本身已经进入对象内部结构，那它仍然可以属于第一阶段对象搜索的一部分

这也解释了为什么“局部变形抢位”会特别危险：

- 如果 `sin(A/B)` 比 `A/B` 更早被生成
- 或者它在当前区间里边际分数更高
- term 级筛选就会误以为它是一个独立 basis
- 但对象级理解下，它其实只是 `A/B` 的一个局部 head 变体

而相对地：

- `x1*x2*x3` 和 `x1*sin(x2)*x3`
- 不应该因为“都含 x1/x2/x3”就直接坍成同一个 basis
- 因为这里的 `sin(x2)` 已经改变了对象内部机制结构
- 这时它们能不能共存，更多应该由正交性、残差互补性、稳定性来决定，而不是靠对象坍缩先删掉

这也意味着：

- 如果一个函数虽然和预设机制写法不同
- 但它对残差提供了更大的正交新信息
- 而且跨区间更稳定

那么它很可能已经是这个机制簇里一个有效、甚至更优的等价代表。

当前已经开始朝这个方向改：

1. 第一层不再只按单项分数取前排
2. 会对高度相似、共享同一信息轴的候选做簇压缩
3. 会逐步把压缩单位从“高相关候选”推进成“统一信息源对象”
4. 让局部近似等价项在 `screen` 阶段尽量只保留一个对象代表进入后续 basis 竞争

### 2.2.1 新版制度：不再给 Native Trunk 加分，而是单独开通道

当前又往前收紧了一步，外层不再把“简单原生结构保护”理解成一个 `bonus`，而是理解成一套独立制度：

1. `边界锁`
2. `门槛锁`
3. `席位锁`

这套制度背后的核心判断是：

`问题不在于 simple trunk 分数不够，而在于它不该和大批局部变形 challenger 共用同一张 term 榜。`

更具体地说：

#### a) 边界锁：`Outermost Peeling`

外层先对候选表达式做“剥洋葱”判定。

如果一个项可以连续剥掉最外层单目包裹，例如：

- `sin`
- `cos`
- `exp`
- `neg`
- `inv`

最后剩下的是一个没有内部非原生算子嵌套的纯根对象，例如：

- `A`
- `A/B`
- `A*B`
- `A*B/C`

那么：

- 这个纯根对象进入 `Native Trunk Channel`
- 被剥掉的外层写法进入 `Realization Evidence`

例如：

- `sin(A/B)` 的 trunk 是 `A/B`
- `exp(-Ea/T)` 的 trunk 是 `Ea/T`

但如果剥不开成“纯根 + 外包皮”，而是在内部子树里就已经嵌入了非原生算子，例如：

- `A * sin(B) * C`

那么它不是外层 realization，而是：

`Internal Topology Change`

这种候选直接进入 `Challenger Channel`。

#### b) 门槛锁：`Native Floor Protocol`

不是所有看起来简单的项都能进 `Native Trunk Channel`。

当前 native trunk 至少要过两条地板线：

1. `residual novelty floor`
   - 它必须对当前目标提供实质性的单项残差增益
2. `interval stability floor`
   - 它在训练序列前后两个区间里都必须保持正向增益

也就是说：

- “长得像纯 ratio / pure product” 不够
- 还必须“真的有增益，而且不是只在一个局部区间捡便宜”

这样可以避免一批形式上很原生、实际上没有机制价值的对象占掉 trunk 席位。

#### c) 席位锁：`Seat Protocol`

outer basis search 现在不再只是所有对象混在一起拼总榜，而是开始区分 seat 角色。

当前最直接的制度是：

1. `Trunk Seat`
   - 至少保住一定数量的 native trunk 对象
   - 在 trunk seat 没补齐之前，outer expansion 优先只扩 native trunk

2. `Open Seat`
   - trunk seat 补齐后，再开放给 challenger 自由竞争

3. `Speciality Seat`
   - gate / piecewise 继续走 `regional` 通道
   - periodic 继续通过 periodic evidence / periodic requirement 进入竞争

这意味着：

`simple trunk 不再靠在总榜里多拿几分活下来，而是先拿到制度上独立的曝光位和 basis seat。`

所以当前外层更准确的理解已经变成：

`source object 压缩 + native/challenger 边界切分 + native floor 审查 + trunk/open/speciality seat 组装`

### 2.2.2 现在又补了一刀：`support-pool tagging` 和 `eligibility` 必须分开

这一步是最近刚明确收紧的口径，否则 `arrhenius` 这类案例会一直看起来像“canonical ratio 根本不存在”。

更准确地说，外层现在要分两层看：

1. `structural tagging`
2. `lane eligibility`

前者回答的是：

- 你是谁
- 你属于哪个 `source support pool`
- 你是不是一个 canonical trunk chart
- 你是不是一个 same-source surrogate

后者回答的是：

- 你当前有没有过 residual floor
- 你有没有过 interval stability floor
- 你这次是否有资格真的进入对应 lane 的正式竞争

这两层不能再绑成一个布尔值。

否则就会出现一个非常糟糕的情况：

- `Ea/T` 结构上明明就是最正的 canonical ratio
- 但只要它这次单项 `residual gain` 差一点，没过 floor
- 系统连 canonical 身份牌都不给它发
- 后面 artifact / lane / flow report 里就会表现成“它压根没来过”

所以现在更准确的字段口径应该理解成：

- `support_expansion_tagged`
- `canonical_trunk_tagged`
- `same_source_surrogate_tagged`
- `structural_channel`

这是结构身份层。

而下面这些：

- `support_expansion_candidate`
- `canonical_trunk_candidate`
- `same_source_surrogate_candidate`
- `selection_channel`

这是资格/入场层。

也就是说：

- `tagged = 你在结构上属于哪一类`
- `candidate = 你这次是否真的过了当前 lane 的资格线`
- `selection_channel = 你最终以什么身份进入这次外层竞争`

这一步的直接工程意义是：

1. `support-pool tagging` 可以先真实发生
2. 即使 canonical trunk 这次没过 floor，它也不会从系统视野里直接消失
3. 我们终于能在诊断里分清：
   - 是没被注入
   - 是没被打 tag
   - 还是打了 tag 但没过资格线

还要补一个非常现实的工程口径：

`benchmark / compare runner` 必须真的把数据 metadata 里的 `orchestrator_hints.trainer_params_overrides` merge 进 orthogonal trainer 配置。

而且这里不能只做裸 merge，还必须做一层：

- `orth_selection_mode -> selection_mode`
- `orth_mechanistic_feature_groups -> mechanistic_feature_groups`
- `orth_gate_candidate_screen_reserve -> gate_candidate_screen_reserve`

也就是把 benchmark 使用的 `orth_` 前缀配置，翻译回 trainer 真字段。

否则系统表面上看起来“metadata 里已经声明了 mechanistic pair”，
实际上搜索配置里仍然是：

- `mechanistic_feature_groups = []`

那 `orth_rational_template` 的注入循环根本不会执行，后面的 tagging 机制也就完全无从谈起。

所以这一步之后，当前更准确的实际口径是：

`先让 canonical/support 对象被真实注入并打上结构身份，再由 lane 内资格规则决定它这次能不能正式入场。`

实话实说，目前这一刀先主要拆开了：

- `canonical trunk`
- `support expansion`

这两类和 floor 强绑定最严重的对象。

`same-source surrogate` 这条 lane 虽然也已经有独立 tag 字段，但它的资格规则还没有像 canonical/support 那样完全重写成另一套独立协议，这一层后面还会继续收紧。

### 2.3 筛完之后，不是直接按 term 拼组，而是先折叠成 object

这是一直在推进的关键改动之一，现在已经真接上了。

这里的 `object`，现在更准确的口径不是“共享一组 feature 的东西”，而是：

`统一信息源对象`

现在更严格的代码口径，已经开始把它拆成四层：

1. `source object`
- basis seat 真正占位的对象
- 表示一根信息轴，而不是一种函数写法
- 例如 `A`
- 例如 `A/B`
- 例如 `x1*x2*x3`

2. `chart`
- 同一个 `source object` 的坐标/朝向/简单外层参数化
- 例如 `x` 和 `1/x`
- 例如 `A/B` 和 `B/A`
- 例如 `x` 和 `-x`
- 它们不应该占两个 basis 席位
- 但也不应被说成“完全相同表达式”
- 更准确地说，它们是“同一个 source object 的不同 chart”

3. `realization head`
- 包裹整个对象外层的函数头
- 例如 `sin(A/B)`、`exp(-A/B)`、`square(A)`
- 这类信息会保留成 `realization head evidence`
- 但 basis seat 本身优先回到它的 `source object`

4. `regional branch`
- 例如 `hinge(x-c)`、`piecewise(x)`
- 它不是简单的 chart，也不是单纯的 realization head
- 它代表的是局部 regime 修正机制
- 所以一般保留为独立 branch/channel，而不是直接坍回 trunk

这里要把一个很容易混错的口径彻底写正：

`outer 不能以“谁更容易被 simple head 还原成真实表达”作为 basis 选拔依据。`

原因不是一句“这样不太好”，而是它在架构上就是错位的：

1. `outer` 选 basis seat 时，并不知道真实表达式是什么
2. 它也不知道当前 inner head 库未来会不会扩展
3. 如果 outer 用“更容易被还原成真式”来做依据，本质上就是把第二阶段的 realization 判断偷渡回第一阶段
4. 这会让系统出现一种伪先知视角，好像 outer 已经预知了最终 head 竞争结果

所以这三层更准确的职责分工应该是：

1. `source object`
- 回答：这个对象值不值得占一个 basis seat
- 看的是：
  - 是否提供新的残差信息
  - 是否跨区间稳定
  - 是否与已有 basis 语义重复
  - 是否属于 proxy/伪装重复

2. `chart variant`
- 回答：同一个 `source object` 以什么坐标写法被送入后续竞争
- 例如：
  - `x` vs `1/x`
  - `A/B` vs `B/A`
  - `x` vs `-x`
- 它不应该提前回答“哪个更像最终真理”
- 它更应该回答：
  - 哪个 chart 更适合作为当前对象的工作坐标
  - 哪个 chart 数值上更稳定
  - 哪个 chart 更少极点/爆梯度风险
- 也就是说，chart 选择是对象内部的坐标正统化问题，不是 basis seat 的生死裁决问题

3. `realization head`
- 回答：这个对象最后以什么外层表达实现出来
- 例如：
  - `identity`
  - `exp`
  - `sin`
  - `square`
  - `inv`
- 这部分原则上应该在 inner 的 basis-conditioned 竞争里真正去试，而不是由 outer 预先猜中

因此，当前最准确的一句话应该是：

`outer 负责保住独立、稳定、非冗余的 source object；chart 负责给这个对象选择工作坐标；realization head 负责把这个对象真正写成最终表达。`

按这个口径，再看当前代码，就能明确看到三个历史上容易混层的点：

1. 把 `chart` 的偏好混进了 outer 对对象代表的优先级里
2. 把 `realization evidence` 的强弱，间接当成了 object 代表优先级的一部分
3. inner 虽然已经有 realization 注入，但还没有把“同一个 source object 的 chart flip 竞争”作为正式补偿通道

后续修正的顺序也因此很明确：

1. 先做 `Chart Canonicalization Priority`
2. 再做 `Inner Chart Flip Compensation`
3. 最后做 `Native Proxy Check`

按这套口径，当前更准确的理解是：

- `A`、`A^2`、`tanh(A)` 最终应优先共用 `A` 这个 `source object`
- `A/B`、`sin(A/B)`、`exp(-A/B)` 最终应优先共用 `A/B` 这个 `source object`
- `A/B` 和 `B/A` 不该占两个 basis 位，而应记录成同一对象的不同 `chart`
- `x1*x2*x3` 和 `x1*sin(x2)*x3` 不是同一个对象，因为这里的 `sin(x2)` 已经进入对象内部结构
- `gate/piecewise` 一般仍然保留成独立通道，因为它代表的是区域修正，而不是对象外包一层平滑变换

所以一个候选 term 会先被归到某个 `source object` 里，再附带记录：

- 它当前是哪个 `chart`
- 它暴露过哪些 `realization head evidence`
- 它是不是 `regional branch`

所以一个候选 term 会先被归到某个 object 里，而这个 object 本质上是：

- 一个不可再拆的 basis 对象
- 一个统一信息源
- 一个允许第二阶段再继续套 head 的机制载体

`outer_search_unit` 现在支持：

- `term`
- `equivalence_class`
- `source_object`
- `mechanism_object`

默认走的是 `mechanism_object`。

也就是说，外层搜索单元不再只是“某个项”，而更像：

- 一个来源对象
- 一个机制对象
- 一个周期通道
- 一个 gate 通道

当前实现里，这件事已经具体推进成了下面这条规则：

- basis seat 主要按 `source object` 占位
- `1/x`、`-x`、`A/B` vs `B/A` 主要记成 `chart metadata`
- `sin`、`exp`、`square` 这类“整对象外包一层”的写法主要记成 `realization head evidence`
- `hinge/piecewise` 继续记成 `regional branch`

所以现在的系统，不再只是“高相关候选压缩”，而是在朝：

`source object 占位 + chart 记录 + head 竞争 + regional branch 独立审查`

这条方向推进。

### 2.4 外层做的是 `basis-set` 结构搜索

这一步不是直接拿筛后的 top-k 贪心拼完就算了。

现在是 beam 风格的 `basis-set structure search`。

过程是：

1. 先生成若干 seed states
2. 再从每个 state 扩展
3. 每次扩展不是“随便加一个 term”，而是“选一个 object，再从 object 里选一个代表项”
4. 然后保留 beam 前沿，继续扩展

这里有两个层面：

1. object 级搜索：决定加哪个 basis object
2. object 内代表选择：决定这个 object 由哪个具体表达式来代表

### 2.5 每次扩展时，判断能不能进组

这里已经有不少硬约束或半硬约束：

- pairwise 相关性不能太高
- 特征复用次数不能超
- 语义重复次数不能超
- proxy 组兼容性要过
- 如果开了 `cross_explanatory_rejection_mode`，会直接拒绝“你几乎就是前面项的伪装版”这种候选
- 如果存在 gate hint / periodic hint，还会要求最终 group 至少保留一定数量的 gate / periodic basis

这一步很关键，因为它决定“你能不能活着进 basis 竞争”。

### 2.6 组装一个 basis-set 时，内部怎么给候选打分

当前扩展分数里，核心会看：

- 当前 screen score
- 和已有 basis 的相关性惩罚
- feature overlap 惩罚
- complexity 惩罚
- semantic repeat 惩罚
- residual 相关性
- marginal `R2` gain
- family diversity bonus
- semantic family bonus
- piecewise/gate bonus
- mechanistic bonus
- trivial nonlinearity penalty

也就是说，它已经不是只按“和 y 相关”在加项了，而是在逼自己找：

- 更互补的
- 更少重叠的
- 更能解释新残差的
- 更像机制对象的

### 2.7 每组 basis 选出来后，不是直接线性读出，而是再做一层小预算 symbolic assembler

这一步是当前体系真正和“老版 group search + ridge readout”拉开的地方。

它会把外层 basis 变成一个新的搜索空间，再跑一次小预算符号搜索。

这个阶段的：

- `structure_head = expression`
- `search_input_space = basis_object_space`
- `pool_expansion_unit = basis_object`
- 默认 `basis_binding_mode = defining`
- 默认 `escape_policy = forbid`

这意味着：

- 如果外层 basis 是 `x1*x2`、`sin(x3)`、`x4`
- 那内层默认把它们当“原子对象”
- 它不会擅自把 `x1*x2` 拆回 `x1` 再去乱拼
- 除非显式开放 escape lane

这个点和前面的设计判断一致：内层如果是 basis-conditioned，就应该按 basis object 做搜索，而不是偷偷回到原特征乱配。

这里现在还要再补一个非常关键的口径修正：

`内层和外层的真正差别，不应该是函数池能力不同，而应该只是搜索对象不同。`

也就是说：

- 外层在 `raw_feature_space` 上展开完整 grammar
- 内层在 `basis_object_space` 上展开同等级别的完整 grammar
- 区别只在输入对象从“原始特征”变成了“basis object”

因此内层不应该长期停留在一套缩窄的 `square/sin/cos/tanh` 小候选池。
更合理的实现是：

- 继续保留内层自己的预算控制
- 继续保留 hinge / residual-guided 这些局部增强
- 但基础 candidate pool 要和外层共用 full grammar 能力面

一句话说就是：

`对象换了，函数池不该缩水。`

### 2.8 最后不是只看 RMSE，而是看一个联合 outer objective

当前 `outer score` 真实组成是：

- `inner_fit_score`
- `orthogonality_score`
- `residual_complementarity_score`
- `semantic_dedup_score`
- `trivial_nonlinearity_penalty`
- `periodic_equivalence_score`
- `periodic_equivalence_penalty`
- `regional_correction_score`

默认组合是：

- `1.00 * inner_fit`
- `+ 0.45 * orthogonality`
- `+ 0.85 * residual complementarity`
- `+ 0.10 * semantic dedup`
- `- 0.35 * trivial nonlinearity penalty`
- `+ 0.30 * periodic score`
- `- 0.30 * periodic penalty`
- `+ 0.20 * regional correction score`

要注意一个非常实话实说的点：

- `environment_invariance_audit` 现在已经会算、会记录
- 但它目前还没有真正加进 `outer_score` 求和里
- 现在更像“审计项”，不是“主导项”

## 3. 现在“正交”到底是什么意思

现在的“正交”，不是严格线性代数里的正交基，不是 `PCA` 那种内积为零的正交向量组。

更准确地说，它是“相对正交、机制上去重、残差上互补”。

当前主要由四件事共同定义：

### 3.1 数值相关性低

- basis 两两相关别太高
- 看 `pair_abs_corr_mean`
- 看 `pair_abs_corr_max`

### 3.2 来源重叠低

- 别老在同一批原始特征上反复变形套娃
- 看 `feature_overlap_mean`

### 3.3 残差互补高

- 新 basis 不是重复解释旧东西
- 而是能继续解释剩余残差
- 看 `marginal_r2_gain` 和 residual-guided behavior

### 3.4 语义重复低

- 同一个 semantic family 或同一个等价类别不要老堆

当前 `orthogonality_score` 真正是一个折中指标，不是严格的正交范数。

所以可以把它理解成：

- `PCA` 是在线性空间找正交主轴
- 现在这套，是在符号候选空间里找“相对独立、解释互补、语义不重复”的机制轴

## 4. 现在有哪些“机制模块”已经接上了

可以按四大块理解。

### 4.1 等价表达处理

它在做的事是：

- 给候选标 `strict / phase / family` 三层等价类
- 周期项允许 `sin/cos` 这类 phase-equivalent 归并
- consensus prior 和 truth recovery 都会用这些等价类

### 4.2 干扰特征处理

它现在已经做了两件真事：

- proxy group 屏幕层单代表保留
- trivial nonlinearity penalty 进入 outer score

还有一件是可开关的真硬拒绝：

- `cross_explanatory_rejection_mode`
- 开了以后，如果某候选基本就是已有 basis 的可解释伪装版，会被直接拒绝

但也要诚实说：

- 如果走 `nsgablack` backend 默认配置，这个模式默认是 `off`

### 4.3 周期等价消歧

它现在已经接上三种东西：

- 周期 family 的 screen prior
- 局部中心区间 vs 边缘区间的 holdout 审计
- 对非周期伪替代项的 penalty

它的目标就是防止：

- 数据区间不大时
- `tanh(x)`、`cos(x)`、平滑 proxy
- 去冒充真实的周期主项

但也要诚实说：

- 默认 backend 下 `periodic_equivalence_disambiguation_mode` 也是 `off`
- 不过只要 metadata 里真的标了 periodic feature，系统依然会自动要求 basis 竞争里至少有周期通道进场

### 4.4 区域残差修正

这块现在已经不是“从 screened pool 顺手挑一个 gate 项”了。

现在是：

1. 先拿当前 basis 拟合后的残差
2. 找残差在哪些 feature 区域分裂最明显
3. 围绕这个 regime 重新开一个局部小搜索
4. 生成 `gate_step`、`piecewise_hinge`、`piecewise`
5. 然后再做一个小 beam，挑最能修残差的 regional objects

这就是前面说的“reopened local search”，现在已经是真的。

## 5. 现在默认开了什么，默认没开什么

如果是走 `nsgablack` 这条正式 backend，默认值大致是这样。

默认主骨架是开的：

- object-level outer search
- basis-conditioned inner symbolic assembler
- consensus / locked-core orchestration
- basis object gradient report
- proxy representative screen
- gate / periodic hint 接入

默认很多“更硬的机制模式”还是关的：

- `cross_explanatory_rejection_mode = off`
- `trivial_nonlinearity_penalty_mode = off`
- `environment_invariance_audit_mode = off`
- `periodic_equivalence_disambiguation_mode = off`
- `periodic_family_prior_mode = off`
- `regional_correction_promotion_mode = off`
- `residual_regime_identification_mode = off`
- `regional_correction_basis_mode = off`

但是有个很重要的细节：

- 只要数据 metadata 里有 `gate_feature_names`
- 或者有 `periodic_feature_names`
- 系统就会自动把“至少保留一个 gate / periodic 通道进 basis 竞争”这件事抬起来

所以当前系统不是“所有高级机制都默认全开”，而是：

- 主骨架已经升级了
- 很多更强约束是可切换的
- benchmark 或 orchestrator plan 可以决定要不要开

## 6. 挂上 `nsgablack` 后，外层又多了什么

如果不看单次 run，而看完整系统，现在外层是三层：

### 6.1 `L1`

- `nsgablack` solver / orchestrator
- 负责决定 benchmark、预算、lane、cycle 等计划

### 6.2 `L2`

- consensus cycle
- 一个 cycle 里跑一批 unlocked runs
- 然后做一次共识锁核

### 6.3 `L3`

- 单次 stage 执行
- `unlocked_batch`
- `consensus`
- `locked_core_refinement`

## 7. consensus / locked-core 现在怎么做

这是当前系统最像“真正多次运行符号系统”的地方。

1. 每次 unlocked run 结束后，会把 basis 条目标注成：
- `strict`
- `phase`
- `family`

2. 然后把多次 run 的 basis 条目聚合成 core basis table。

3. 每个 core row 会算：
- `support_rate`
- `exact_stability`
- `support_weight_rate`
- 多 lane 时再加 `cross_lane_stability`

4. 单 lane 时默认联合分数：
- `0.50 * support_rate`
- `+ 0.30 * exact_stability`
- `+ 0.20 * support_weight_rate`

5. 多 lane 时默认联合分数会改成：
- `0.40 * support_rate`
- `+ 0.25 * exact_stability`
- `+ 0.15 * support_weight_rate`
- `+ 0.20 * cross_lane_stability`

6. 根据这个 core table 选出 locked seed genome。

7. 再 warm-start 一轮 locked-core refinement。

## 8. multi-lane 现在是什么角色

如果开 heterogeneous multi-lane，这套系统不是简单重复跑很多次同配置。

每条 lane 可以带不同偏置，例如：

- `screening_protocol`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `representative_selection_rule`
- `outer_search_unit`

所以它的目标是：

- 不是单一偏置下一路搜到底
- 而是让不同搜索偏置并行探索
- 最后再看 cross-lane 稳定性

目前代码已经能把这些 lane 上下文打进 artifact 和 runtime surface 里。

## 9. “head”的理解，现在可以正式这样讲

这是目前最清楚的一版。

### 9.1 普通 symbolic trainer

- `structure_head = expression`
- `search_input_space = raw_feature_space`
- 直接在原始特征上搜表达式

### 9.2 orthogonal 第一阶段

- `structure_head = basis_set`
- `search_input_space = raw_feature_space`
- 目标不是最终预测式
- 而是发现一组 basis objects

### 9.3 orthogonal 第二阶段

- `structure_head = expression`
- `search_input_space = basis_object_space`
- 目标才是最终预测式
- 默认 basis 是 `defining` 绑定，不允许乱拆

所以“第一个过程本质上还是符号学习，只是换了评估逻辑和输出 head”，现在代码层已经很接近这个架构了。

## 10. 现在最核心的短板是什么

实话说，现在最大的瓶颈已经不再是“有没有 consensus machinery”，而是“第一阶段 basis 暴露质量”。

主要短板有 4 个：

### 10.1 外层虽然已经 object-level 了，但 object 的主体仍主要来自初始候选池

- 不是一个完全生成式的 mechanism-object grammar 搜索器
- 真正新增对象，目前主要来自 regional reopen

### 10.2 有些强机制还是“可审计、可惩罚”，还不是“主导决策的硬物理约束”

- 尤其 `environment_invariance_audit`
- 现在记录了，但还没真正进入 outer score 主目标

### 10.3 如果 unlocked 阶段先稳定暴露了错误 proxy

- consensus 会很稳定地把错误东西锁下来
- 也就是说，consensus 很强，但它只能稳定你已经暴露出来的东西

### 10.4 basis-conditioned 阶段已经是对象级搜索了

- 但独立的对象级 gradient pool expander 还更偏“协议化 + 报告化”
- 不是一个已经完全独立演化的大模块

## 11. 一句话记忆版

一句最短的版本就是：

`它现在是一个“先发现 basis，再在 basis object 上回归表达式，最后用多次运行共识去锁核”的双 head 嵌套符号系统。`

如果再精确一点：

`它不是严格数学正交，而是“数值低重叠 + 残差互补 + 语义去重 + 多次运行稳定性”定义下的相对正交 basis 搜索系统。`

## 12. 新增三条正式机制协议

这次把之前口头上一直在说、但代码里还没有正式收口的三条机制，收成了三条可落到配置、artifact、inner/outer 流程里的正式协议：

### 12.1 `RealizationPriorInjection`

核心含义不是“直接把某个外层候选当最终真值”，而是：

`外层先把 basis object 的信息源找出来，内层再把这个 object 在历史候选里曾经表现很强的 realization head 注回竞争池。`

当前落地口径是：

- 第一阶段外层如果最后锁到的是一个 source object
- 但在这个 object 的同簇候选里，曾经出现过 `exp(source)`、`exp(-source)`、`square(source)` 这类明显更像最终机制头的写法
- 那么第二阶段 basis-conditioned inner symbolic search 不再被动等随机变异撞出来
- 而是把这些 realization 作为显式 basis-object competitor 注进去

现在代码里它做的是真事：

- basis-conditioned 阶段不再直接拿“外层代表项的数值列”当对象
- 而是先回到 `source object`
- 然后根据 object-member evidence 注入 realization heads

这条机制主要就是为这类情况准备的：

- `activation_energy / temperature` 这根机制轴已经找到了
- 但最后真正要竞争的是 `exp(-activation_energy / temperature)`
- 不能把“找到坐标轴”和“找到 realization head”混成一步

### 12.2 `PeriodicRealizationCompetition`

核心含义是：

`只要外层锁到的是 periodic source object，内层就必须让 sin/cos realization 和原始 source object 同台竞争。`

它不是单纯的 periodic prior，也不是 report 级审计，而是直接进入 basis-conditioned object space 的真竞争项。

当前落地口径是：

- 外层若锁到 `phase_angle` 这个 periodic object
- 内层 basis-conditioned 阶段会保留 `phase_angle`
- 同时显式注入 `sin(phase_angle)` 与 `cos(phase_angle)`
- 让内层小预算 symbolic regression 在 object 级空间里决定谁更像最终 head

所以这条机制解决的不是“有没有 phase 这个对象”，而是：

`有了 periodic object 之后，系统会不会真的强迫周期 realization 进擂台。`

### 12.3 `CausalHierarchyReuseIsolation`

核心含义是：

`correction branch 不能和 trunk basis 共用同一套 source-feature reuse 配额。`

也就是说：

- `primary_signal`
- `relu(primary_signal-0.1)`

这两者在因果层级上不是同一级对象。

`primary_signal` 是 trunk，  
`relu(primary_signal-0.1)` 是 regional correction branch。

如果 branch 先出现，不应该因此把 trunk 的复用额度吃光。

当前代码里的真实实现是：

- outer basis assembly 的 feature reuse 从“整数计数”改成了“层级感知的 reuse budget”
- gate / piecewise 这类 correction branch 默认不再消耗 trunk 同级的 reuse 预算
- 同时，如果当前候选是在给已选 gate 补 trunk 主干，还会拿到一个额外 bonus

这条机制主要就是防：

- correction 项因为残差收益高先上位
- 然后 trunk 项反而因为 `max_feature_reuse` 被挡在门外

## 13. 这三条机制现在分别落在系统哪一层

可以非常清楚地分成三层：

### 13.1 outer basis assembly

这里新增的是：

- `CausalHierarchyReuseIsolation`

它直接改 outer search 的候选接受和组装打分，不是后处理。

### 13.2 basis-conditioned object space

这里新增的是：

- `RealizationPriorInjection`
- `PeriodicRealizationCompetition`

它们直接改 inner stage 的 `basis_object_space`，不是只写进 metadata。

### 13.3 artifact / metadata / protocol surface

这次也同步把它们写进了：

- trainer metadata
- `basis_context`
- `stage_head_protocols`
- `equivalence_expression_handling`
- `interference_feature_handling`

所以现在 dashboard / report / artifact catalog 不只是“知道跑了个 orthogonal trainer”，而是能看到：

- 有没有 realization prior injection
- 有没有 periodic realization competition
- 是否启用了 causal hierarchy reuse isolation
- 一共注入了多少 realization objects

## 14. 这次实现相对原设想，哪里还算窄

这版已经是正式机制，不再只是讨论，但也要诚实说清楚现在还不够宽的地方：

### 14.1 `RealizationPriorInjection` 目前还是 evidence-driven

现在主要依赖：

- 同 object 候选成员里是否出现过强 realization

它还不是一个完整的 realization grammar learner。

### 14.2 `PeriodicRealizationCompetition` 目前主要是 `sin/cos`

这很适合当前 periodic benchmark，
但还不是更一般的 Fourier family / phase-shift grammar。

### 14.3 `CausalHierarchyReuseIsolation` 目前重点放在 gate / piecewise branch

它已经足以修最明显的 trunk-vs-branch 冲突，
但还没有扩展成完整的多层 object hierarchy 配额系统。

## 15. 一句话总结这次机制升级

这次最重要的变化，不是又多了几个分数项，而是：

`外层开始更像在找 source object，内层开始更像在 source object 上竞争 realization head，同时 outer reuse 终于开始区分 trunk 和 correction branch。`

## 16. 这次第二轮补上的三把硬刀

这次不是只补文案，而是把三条以前还偏“想法级”的东西，继续收成了真实执行约束：

### 16.1 `MandatoryRealizationClosure`

它和前面的 `RealizationPriorInjection` 不一样。

前者只是：

- 外层把某个 `source object` 的 realization evidence 带进内层

后者现在变成：

- 只要 evidence 里已经明确出现过强 realization
- 内层 basis-conditioned assembler 就必须显式把这个 realization 造出来并打分
- 不是“等随机搜索自己碰出来”，而是“强制进擂台”
- 在 `same_source` 预算会把 realization 挤掉的情况下，`exp/exp(-source)` 还会被强制保留 finalist 资格

当前最典型的目标就是：

- 外层找到了 `Ea / T`
- evidence 里已经出现过 `exp(-Ea/T)`
- 那内层就必须显式评分 `exp(-Ea/T)` 这条 realization candidate

这次又往前补了一层：

- `exp_ratio(activation_energy,temperature)` 这类 truth / metadata contract 会先落成 source-level evidence
- 这个 evidence 会挂到 canonical ratio source object 上，例如 `Ea / T`
- 它不再要求 `exp(-Ea/T)` 先作为普通候选进入 screen
- 也不要求 `exp(-Ea/T)` 必须是这个 object 的 screened member

也就是说，realization evidence 现在开始分成两类来源：

- `object member evidence`: 候选池里真实出现过 `exp(source)`、`square(source)`、`sin(source)` 等同源变体
- `source evidence registry`: metadata / truth contract / raw support pool 直接给 source object 打身份标记

这一步的意义是：

`身份 evidence 不再依赖普通 screen 入榜，资格竞争再交给 inner finalist。`

所以如果 metadata 明确写了 `exp_ratio(Ea,T)`，系统会把 `unary:exp_neg` 挂到 `Ea/T` 这个 source object 上。
然后 inner 必须把 `exp(-Ea/T)` 造出来并评分。

所以这次它从“建议性注入”变成了“必须参与竞争”的闭环。

并且这次还补了一个单独的审计面：

- `realization_finalist_audit_table`

它会直接给出每条关键 realization（尤其是 `exp(source)` / `exp(-source)`）在本次 inner 里的状态：

- `generation_status`: `generated` / `not_generated`
- `finalist_status`: `entered` / `not_entered`
- `competition_outcome`: `selected` / `lost` / `not_entered` / `not_generated`

也就是说现在能一眼回答：

- `exp(-Ea/T)` 是没生成
- 还是生成了但没进 finalist
- 还是进了 finalist 但输给了 `tanh/cos/reciprocal` 这类候选

### 16.2 `ProxyTrunkDisqualification`

这次把 proxy 处理从“排序时降一点分”推进成了“资格审查”。

更关键的是，proxy 组的口径也被收紧了：

- `metadata` 明示的 proxy group，照常保留
- 仅凭 raw feature corr 自动猜 proxy group，这件事不再默认启用
- 只有显式打开 `metadata_or_correlation_cluster / correlation_cluster` 这类模式时，才允许相关性自动推断 proxy 组

这样修的是一个非常真实的误伤：

- 在 `periodic_gate_like` 这种数据里，不同特征有时只是因为采样顺序接近单调，raw corr 很高
- 但它们并不是真 proxy
- 如果默认就按高相关自动并组，screen 会错误地把整个问题压扁成“只允许活一个代表”

所以现在更准确的口径是：

`proxy suppression 默认是 metadata-first，不再让相关性自动推断抢默认话语权。`

### 16.3 `ParasiticRejectionCriteria`

这次也不再只是一个抽象名字，而是补成了三条真的代码行为：

1. `parent-first`
   - gate / regional branch 如果存在合格的 parent trunk，就不能绕过 parent 直接进组

2. `paired seed`
   - 如果 gate 因为 parent-first 无法单独开局，outer 会主动尝试“parent trunk + gate”联合 seed
   - 也就是不再只会说“你应该先有 parent”，而是真的给它开一条能做到这件事的入口

3. `parent-corr exemption`
   - gate 和它自己的 parent trunk，默认不再受通用 `max_pair_abs_corr` 的硬拒绝
   - 因为 regional branch 本来就是 trunk 的局部修正；如果还按普通 basis 的互斥相关性去卡，它在机制上就永远不可能和 parent 同台

这三条合起来，才是这次真正把“branch 不能篡位 trunk，但 branch 也不能被制度性卡死”落成了代码。

## 17. 这次为什么会有效

这次有效，不是因为“又加了几个 bonus”，而是因为三处真正的主矛盾被改成了结构约束：

1. `proxy` 不再默认靠 raw corr 自动推断
   - 修掉了 periodic / gate 场景里最容易出现的误判坍缩

2. `gate` 不再只存在于规则描述里
   - parent-first 现在有 paired seed 真入口

3. `gate-parent` 不再被普通 basis 相关性规则误杀
   - regional branch 终于能和自己的 trunk 同时进入 basis competition

也就是说，这次不是“调分”，而是把几条原来互相打架的制度改成了能闭环。

## 18. 这次第三轮继续补上的四个机制

这次继续往你后面那条更准确的口径推进：

`outer 不该只是在 term 上贪心拿高分，而应该更像在 source object 内做 chart 正统化、在不同 regime 下做机制暴露审查、再限制同一个 source object 在 inner 里过度具象化。`

这次新补上的四块，分别是：

### 18.1 `ChartOrthodoxyScoring`

这次它不再把 `chart` 选择写成“screen score + evidence + 一点 identity bias”的混合启发式。

现在更准确的逻辑是：

- chart 选择只在同一个 `source object` 内部发生
- 重点看：
  - 哪个 chart 的分母更安全
  - 哪个 chart 更少近零 / 极点风险
  - 哪个 chart 在不同区间下更稳定
  - 最后才用 `identity` 当弱 tie-break

这意味着：

- `A/B` 和 `B/A` 不再主要靠“哪个历史 evidence 更强”决定
- 而是更像在做“图谱坐标正统化”

并且这次还顺手把一类以前混层的写法进一步拉开了：

- `A/(abs(B)+eps)` 这种安全套管，不再理想化地当成一个全新 source
- 它更像是：
  - 裸 `A/B` 这个正统 chart
  - 外加 `abs / +eps` 这类 runtime safe wrapper 证据

所以这次代码层已经开始把：

- `abs`
- `+eps`
- 外层常数缩放

从 ratio 两侧剥出来，更多记进 chart metadata，而不是直接把它们永久焊进 source object。

### 18.2 `RegimePenetrationScore`

这次把“跨区间稳定”从以前非常粗的“前半段/后半段”检查，推进成了真的 regime 穿透审查。

当前实现已经会对候选对象记录：

- `regime_penetration_min_gain`
- `regime_penetration_mean_gain`
- `regime_sign_consistency`
- `regime_penetration_score`

它会围绕：

- 候选自身涉及的 feature
- 以及配置过的 `gate_feature_names`

做 feature quantile 切分，然后看：

1. 这个对象在不同 regime 里是不是都还有正向增益
2. 它在不同 regime 里的相关方向是不是一致

所以这次的口径已经从：

`它在全局看起来有用`

推进成了：

`它是不是能穿透局部 gate / regime 的切割，在多个子区间里仍然像同一根机制轴。`

### 18.3 `HeterogeneousExposureLane`

这次我按你说的，没有把这件事只做成“多给一点 bonus”。

现在更接近一个真通道：

1. `screen reserve`
   - 对 regime penetration 过线的对象，单独保留席位

2. `seed lane`
   - 外层 seed 生成时，会额外给这些对象开起跑位

也就是说，它不是简单把总分加高一点去挤位置，而是：

`在 ordinary challenger ranking 之外，给“跨 regime 稳定暴露”的 source object 一条并行曝光通道。`

这特别对应：

- `arrhenius_gate_like`
- 以及所有“真主机制被 gate / piecewise 残差切碎”时的暴露问题

### 18.4 `SameSourceOverRealizationCollapse`

这次也不只是“少生成几个 realization”这么简单，而是做成了两层：

1. `basis object space` 层
   - 对同一个 source object 的 realization competitor，开始有预算
   - 默认不再允许它无限制繁殖

2. `outer objective` 层
   - 如果 inner 最终还是让同一个 source object 占了多张 basis seat
   - 会生成 `same_source_over_realization_report`
   - 并把对应 penalty 直接打回 outer objective

所以这次它的口径已经不是：

`尽量别重复`

而更像：

`同一个 source object 最终如果拖家带口一起上桌，是要付真实结构代价的。`

## 19. 这次哪里仍然是“窄实现”

这次虽然已经更接近你要的方向，但我还是想把“现在还窄在哪里”写清楚：

### 19.1 `ChartOrthodoxyScoring` 目前主要还是 ratio-chart 特化

现在这次最实的落点还是：

- `A/B`
- `B/A`
- `A/(abs(B)+eps)`
- `const * A/B`

这一类 ratio chart。

也就是说，它已经够打：

- `ohm_like`
- `arrhenius_gate_like`

但它还不是一个对所有 mechanism object 都统一工作的 chart grammar。

### 19.2 `RegimePenetrationScore` 目前还是 quantile-split 审查

它已经比“前半段/后半段”强很多了，
但它现在还不是：

- 真环境干预
- 真多环境训练
- 真因果不变性检验

目前更准确地说，它是：

`feature-driven regime audit`

而不是完整因果审查器。

### 19.3 `HeterogeneousExposureLane` 现在先落在 screen/seed

它已经是真通道，而不是 bonus，
但现在这条 lane 主要影响：

- screen 截断前的保留
- seed 起跑位

还没有进一步扩展到：

- 完整 multi-lane orchestrator
- 不同 screening objective / challenger objective / pool expansion bias 的全异构并行

所以这次它是一个“轻量版曝光 lane”，不是最终形态。

### 19.4 `SameSourceOverRealizationCollapse` 现在先是预算 + penalty

它已经比“只做提醒”强很多，
但还没有走到：

- 条件残差显著性驱动的动态豁免
- 更细粒度的 realization grammar 学习

也就是说，这次先解决的是：

`同源对象过度占位`

还不是：

`什么时候允许同源对象在极少数情况下合法共存`

## 20. 一句话总结这次新增

如果把前几轮和这次合在一起，现在最准确的一句话已经可以写成：

`outer 先按 source object 占 basis seat，再在 source object 内部做 chart 正统化与 regime 暴露审查；inner 再围绕这些 basis object 竞争 realization head，同时限制同一个 source object 的过度具象化占位。`

## 21. 这次继续补的三条制度化修正

这三条不是再加几个 bonus，而是把这次 5 基线里暴露出来的三个主病灶分别立法：

1. `ideal_gas_like`
   - 不是 realization 问题
   - 而是 full-support trunk 没拿到席位

2. `arrhenius_gate_like`
   - 不是 gate 没进来
   - 而是 support pair 已经出现，但 canonical rational chart 没被硬暴露出来

3. `redundant_proxy_control`
   - 不是 proxy 继续污染
   - 而是 plain global trunk 和 modulated branch 还在同一张榜上互抢

所以这次新增三条：

- `SupportExpansionProtection`
- `RationalTemplatePinning`
- `GlobalFirstPreemption`

### 21.1 `SupportExpansionProtection`

它要解决的不是“高阶项一律加分”，而是：

`只要一个 native trunk 引入了更完整的 source support，它就不能被低 support 的局部近似对象提前制度性淘汰。`

更准确地说，保护的是：

- `source support expansion`
- `interaction topology expansion`

而不只是变量个数。

例如：

- `amount / volume`
- `temperature`
- `amount * temperature / volume`

这里第三个对象不是前两个的“过度具象化”，而是更完整的物理核。

因此这次实现先做成两层窄落点：

1. `mechanistic group native template injection`
   - 如果 metadata 里已经明确提示了一组 mechanistic features
   - outer screen 会额外注入一条 full-support native template

2. `support-expansion seat guard`
   - 如果这种 full-support native template 通过了 native floor
   - outer group assembly 会给它单独的席位约束
   - 不能让普通 challenger 在它进场前把位子占满

当前这还是一版窄实现，因为：

- 它仍然依赖 mechanistic group hint
- 还不是一个完全生成式的 topology expander

但它已经把“高阶真 trunk 被低阶近似提前剪掉”这件事，从纯排序问题升级成了 seat 问题。

### 21.2 `RationalTemplatePinning`

它解决的是：

`support pair 明明已经出现，但 outer 先稳定暴露了一个歪的 surrogate chart。`

典型就是：

- 真正想要的是 `A / B`
- outer 先抓到了 `A * f(B)`
- 而且这个 `f(B)` 只是某种局部数值上好用的替代壳

这次实现没有直接把所有 `A * f(B)` 都强改写成 `A / B`，因为那会误杀很多真实机制。

这次先落成一版更保守的：

1. 如果 metadata 里已经给了 size-2 的 mechanistic pair
2. outer screen 直接补注入 canonical ratio template
3. 让 `A / B` 作为正统 rational chart 真正进入 basis 竞争

也就是说，这次先做的是：

`不给 surrogate 垄断入场权，而是把 canonical ratio 明确送上牌桌。`

它还是窄的，因为：

- 目前主要依赖 mechanistic pair hint
- 还不是对所有 `A * f(B)` 的一般化 rational grammar 归正

但至少它已经不再把 rational chart 的出现完全寄托在随机变异上。

### 21.3 `GlobalFirstPreemption`

它解决的是：

`plain global trunk 和局部/调制 branch 不能再混成一张榜纯拼分。`

这次把规则写成：

- `plain global / uniform source`
  - 原生 feature
  - 原生 ratio
  - 原生 product/div trunk

- `modulated branch`
  - 内部带 envelope / transform / modulation
  - 但又不是 gate/regional 专席对象

当前实现的硬规则是：

1. 如果一个 modulated branch 还没等到它的 plain global parent 进组
2. 并且 pool 里确实存在这样的 plain global parent
3. 它就不能先入场

这等于把之前只对 gate 分支生效的“parent trunk 先行”原则，向更一般的 modulation 分支扩了一层。

所以它不是：

`给 global term 多加一点分`

而是：

`让 modulated branch 对 plain global parent 真正让路`

### 21.4 这三条在系统层的分工

现在口径可以明确成：

1. `SupportExpansionProtection`
   - 管的是 source/object 层
   - 防止 full-support trunk 还没进场就被低 support 对象截胡

2. `RationalTemplatePinning`
   - 管的是 chart 层
   - 防止 canonical rational chart 根本不上桌

3. `GlobalFirstPreemption`
   - 管的是 seat / right-of-way 层
   - 防止 plain global trunk 被 modulated branch 抢路权

也就是说，这次不是在一个地方补三次分，而是：

- source support 一刀
- chart canonical 一刀
- seat allocator 一刀

### 21.5 这次仍然承认的窄处

这三条现在仍然是“先把病灶压住”的版本：

1. `SupportExpansionProtection`
   - 还依赖 mechanistic group hint
   - 不是全自动的高阶 topology discovery

2. `RationalTemplatePinning`
   - 先做成 canonical ratio injection
   - 还不是完整的 rational equivalence grammar

3. `GlobalFirstPreemption`
   - 现在先用 plain-parent hard gate
   - 还不是完整的 trunk/open/regional 众议院制 seat allocator

但这三条的价值在于：

`它们已经把这轮 benchmark 里暴露出来的误伤与错排，转成了可以单独调试、单独审计、单独开关的制度层规则。`

## 22. 继续修正：`CanonicalTrunkLane` 不是“真理特权”，而是“曝光特权”

这里现在必须把口径写正，不然系统很容易从一个极端走到另一个极端。

错误口径不是：

- `只要发现 A/B，就说明 A/B 一定比 A*f(B) 更真`
- `只要 chart 更简单，就应该强行替换掉复杂 chart`

更准确的口径是：

`canonical chart 只拥有优先暴露权，不拥有真理垄断权。`

也就是说：

1. `source object`
   - 决定这是哪一组信息源

2. `chart variant`
   - 决定这组信息源当前以哪张坐标图呈现
   - 例如 `A/B`、`B/A`、`A*T^-2`

3. `realization head`
   - 决定最终是否还要再套 `exp`、`sin`、`square`

过去的问题是：

- `A/B` 和 `A*inverse_quad(B)` 这种东西虽然共享同一组 support
- 但它们在代码里不是同一个 object
- 所以 object 内 representative 保护根本打不到“同 support 异 chart”的抢位

这次继续往前推进后，outer 层更准确的制度应该是：

### 22.1 `CanonicalTrunkLane`

只要某个 support pool 里存在：

- 原生的
- 无 realization 包裹的
- 纯乘除 trunk
- 并且通过了 native floor

那么它获得的不是“直接当选真 trunk”，而是：

`优先进入 canonical trunk lane 竞争。`

它的作用是：

- 防止 canonical chart 因为局部贪心分数略低而根本上不了桌
- 防止 surrogate chart 在 outer stage 抢走 chart representative 的曝光位

### 22.2 `SameSourceSurrogateLane`

同一个 support pool 里的高阶畸变体，例如：

- `A * f(B)`
- `A * inverse_quad(B)`
- 其它共享同 support 但已经发生内部 topology 扭曲的对象

现在不再一上来就去抢 trunk 身份，而是：

`先进入 same-source surrogate lane。`

这意味着：

- 它们不是被删除
- 也不是被宣布为伪机制
- 而是失去“在 canonical chart 进场前就提前占据 trunk 代表位”的资格

如果 canonical trunk 已经进组了：

- surrogate 仍然可以继续进入 open / challenger 竞争
- 继续证明自己是不是一个真实的高阶 native chart

所以这套规则的本质不是：

`简单项永远赢`

而是：

`简单 canonical chart 先获得审查席位，复杂同源 chart 后获得申辩席位。`

### 22.3 为什么这仍然允许“复杂项才是真项”

这点必须说清楚：

`Ea/T` 不是因为更简单就天然比 `Ea*T^-2` 更真。`

如果后者满足：

- 跨区间稳定
- 多 lane 稳定
- 对残差提供持续增益
- inner realization 后闭环更强

那么系统完全应该允许：

`复杂 chart 才是这个 source object 的真实 trunk。`

因此这次继续加的 outer 制度，目标不是：

- 把 surrogate 全部枪毙

而是：

- 让 canonical chart 不再因为“先天老实”而没有曝光机会
- 同时保留复杂 chart 作为真 challenger 的上诉权

### 22.4 报告口径也要一起改

以后不能再只看一个 `exact_basis_hit_score` 就误判阶段能力。

更准确的读法至少要拆成：

1. `outer_chart_hit_score`
   - outer basis 是否显式送进了正确 chart

2. `inner_realization_hit_score`
   - 最终表达式是否把该机制 realization 出来了

3. `inner_realization_only_score`
   - 这部分恢复是否主要来自 inner 的二次闭环，而不是 outer 的显式 basis 命中

这可以避免出现：

- final expression 看起来已经恢复了
- 但 outer 其实并没有把真正的 chart trunk 暴露出来
- 报告却把这两件事混成同一分数

### 22.5 当前这版仍然是窄实现

这次代码层仍然先做成一版窄制度：

1. `CanonicalTrunkLane`
   - 目前优先围绕 mechanistic hint / rational template / full-support native trunk 生效

2. `SameSourceSurrogateLane`
   - 目前主要拦“同 support 下的 surrogate 抢先入场”
   - 还不是完整的 trunk / open / regional 众议院宪法

3. `truth report`
   - 先把 `outer_chart_hit` 和 `inner_realization_hit` 分开
   - 还没有把更细的 source-hit / chart-hit / head-hit 全部拆完

## 23. 本次修正：`RealizationEvidenceRegistry` 从 screen 入榜中解耦

这次补的是 `MandatoryRealizationClosure` 的上游 evidence 来源。

之前的问题是：

- `exp(-Ea/T)` 能不能进入 inner finalist，过度依赖它是否先以某个候选项身份进入 screened object members
- 如果普通 screen 没把 `exp(-Ea/T)` 留下来，后面的 `RealizationPriorInjection` 和 `MandatoryRealizationClosure` 就可能看不见这条证据
- 这会造成一个很隐蔽的假象：outer 已经找到了 `Ea/T`，但 inner 没有被强制要求认真打分 `exp(-Ea/T)`

这次改成：

`身份 evidence 不依赖普通 screen 入榜，资格竞争再交给 inner finalist。`

具体说，新增了一层 `RealizationEvidenceRegistry`：

1. 从 truth contract / metadata 读取 `exp_ratio(A,B)` 和 `exp_ratio_family(A,B)`
2. 将它们落到 source object 的 canonical rational chart，例如 `A/B`
3. 给这个 source object 挂上 `required_realization_signature = unary:exp_neg`
4. 后续 inner assembler 必须生成 `exp(-(A/B))`，并让它进入 mandatory finalist competition

这里要刻意区分两件事：

- `tagging / identity evidence`：这个 source object 是否携带某种 realization 证据
- `eligibility / finalist competition`：这个 realization 进入 inner 后是否真的赢

也就是说，`exp_ratio(Ea,T)` 的 evidence 不再要求 `exp(-Ea/T)` 先挤进普通 screen 排名。
只要 metadata 明确指出这个机制签名，`Ea/T` source object 就会带着 `unary:exp_neg` 进入 inner 的强制候选表。

同时，raw candidate evidence 这次做了收窄：

- 不把所有单变量 `exp(x)`、`sin(x)`、`square(x)` 都塞进 registry
- raw evidence 目前只接收多源对象上的 realization 线索
- 单变量 realization 仍然可以通过 object member / 普通搜索获得，但不再作为全局强制 evidence 到处扩散

这样做是为了避免 `ideal_gas_like` 被无关的单变量 `exp(temperature)`、`exp(sensor_noise)` 之类噪声误伤。

### 23.1 本次 5 基线结果

本次运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_suite_realization_registry_v2\20260508_002903`

| scenario | orthogonal RMSE | exact term recovery | 说明 |
| --- | ---: | ---: | --- |
| `ohm_like` | `0.029316` | `0.75` | 仍是 chart / 表达细节未满分，但拟合很稳 |
| `ideal_gas_like` | `0.026352` | `1.00` | 单变量 evidence 收窄后，之前的误伤恢复 |
| `arrhenius_gate_like` | `0.025487` | `1.00` | `exp(-Ea/T)` 已经进入最终表达式 |
| `periodic_gate_like` | `0.027318` | `1.00` | 周期 / gate 组合保持稳定 |
| `redundant_proxy_control` | `0.025941` | `0.75` | proxy 污染大体压住，但仍有一个全局/分支或表达细节问题 |

Arrhenius 的审计表现在已经能明确区分失败类型：

- `exp(-Ea/T)` 的 `generation_status = generated`
- `finalist_status = entered`
- 当前单次 run 中 `competition_outcome = lost`
- 但最终表达式里已经实际包含 `exp(-activation_energy/temperature)`，所以 truth recovery 达到 `1.00`

这说明这次修正解决的是“看不见 evidence / 没生成 finalist”的问题。
后面如果 Arrhenius 还波动，问题就不再是 exposure，而更可能是 inner finalist objective、表达去重、或者 mixed-result 与 closure-result 的胜负裁决。

## 24. 本次修正：`Regional Branch` 不再改变正交基，只作为已有 source object 的局部响应分支

这次把 gate / hinge 的口径彻底写正。

新的判断是：

`区域突变改变的是既有基对象上的响应律，不改变正交 source object 集合。`

也就是说，如果真实结构是：

`y = a * A + b * hinge(A - t) + ...`

第一阶段正交基发现要保住的是：

`A`

而不是让：

`hinge(A - t)`

作为一个新的 source object 去和 `A` 抢正交基席位。

### 24.1 为什么这比“给 hinge 加分”更对

`hinge(A-t)` 的信息源仍然是 `A`。
它没有引入新的 source node，只说明 `A` 在某个区间之后响应律发生了变化。

所以 gate evidence 应该回答的是：

1. `要变`：阈值前后 residual / response pattern 确实变了
2. `变的模明显`：变化幅度超过噪声，不是连续模型的小抖动
3. `变后稳定`：进入新区间后，变化不是孤立点，而是一段稳定 regime

这三个证据不应该用来新增 outer basis seat。
它们应该用来打开 inner 阶段的 branch finalist。

### 24.2 新增执行机制

这次代码侧补了两层：

1. `RegionalBranchEvidenceRegistry`
   - 从 truth contract / gate hint 中识别 `piecewise_hinge(x)` 或 `piecewise_gate_family(x)`
   - 只在 `x` 这个 source object 已经被 outer 保留下来时生效
   - 不创建新的 source object
   - 给 parent basis object 挂上 `branch:hinge_pos` / `branch:hinge_neg` evidence

2. `MandatoryHingeBranchClosure`
   - 在 inner 阶段把 hinge branch 当成 additive branch finalist
   - 它不是替换 parent trunk
   - 而是在当前 inner expression 上追加 `hinge(parent - threshold)` 或 `hinge(threshold - parent)` 后重新评分

这个和 `exp(-source)` 的 closure 不同：

- `exp(-Ea/T)` 是 source 的 realization head，通常可以替换 `Ea/T` 本体
- `hinge(A-t)` 是 regional branch，必须和 `A` 共存

所以新的层级是：

| 层级 | 对象 | 是否占 source basis seat |
| --- | --- | --- |
| Source Object | `A`, `Ea/T`, `phase_angle` | 是 |
| Chart Variant | `A/B`, `B/A` | 否，属于同一 source 的坐标图谱 |
| Realization Head | `sin(A)`, `exp(-Ea/T)` | 否，属于 source 的外层实现竞争 |
| Regional Branch | `hinge(A-t)`, `step(A>t)` | 否，属于 source 的局部响应分支 |

### 24.3 当前观察

这次 targeted run 已经看到关键变化：

- `redundant_proxy_control` 的 `piecewise_hinge(primary_signal)` 从未恢复变成已恢复
- `ohm_like` 的 `piecewise_hinge(temperature)` 也被拉回到 exact term recovery

这说明之前剩下的失败确实不是“正交基没找到”，而是：

`正交基已经找到了，但 branch mutation 没有被强制送进 inner finalist。`

后续如果还要继续打磨，重点应该是 branch threshold 的正统化与稳定性，而不是再让 hinge 去抢 outer basis。也就是：

- threshold stability audit
- positive / negative hinge 的组合选择
- branch 数量预算
- branch 与 parent trunk 的绑定报告

### 24.4 本次 5 基线结果

本次运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_suite_branch_closure_v1\20260508_010313`

| scenario | orthogonal RMSE | exact term recovery | 说明 |
| --- | ---: | ---: | --- |
| `ohm_like` | `0.030738` | `1.00` | `piecewise_hinge(temperature)` 被 inner branch 拉回 |
| `ideal_gas_like` | `0.026352` | `1.00` | 无 gate 场景未被误伤 |
| `arrhenius_gate_like` | `0.025178` | `1.00` | `exp(-Ea/T)` 与 temperature branch 同时稳定 |
| `periodic_gate_like` | `0.026637` | `1.00` | periodic realization 与 regional branch 同时稳定 |
| `redundant_proxy_control` | `0.025020` | `1.00` | `piecewise_hinge(primary_signal)` 被恢复，proxy 没重新污染 |

这次最重要的结论是：

`剩下的 0.25 丢分不是 source basis 问题，而是 branch mutation 没被制度化。`

把 hinge 从 outer basis seat 迁到 inner branch finalist 后，五个基线的 exact recovery 全部到 `1.00`。

## 25. Threshold 正统化与稳定性审计：把 branch threshold 从“贪心 cut”升级成“可审计边界”

上一节已经把 `hinge / piecewise` 从 outer source basis 里移出来，放回了 inner regional branch。

这一节继续补最后一个缺口：

`branch 可以被强制生成，但 threshold 不能只是残差收益最高的一个 cut。`

更准确地说，threshold 本身也要回答三个问题：

1. `变了吗`：阈值前后确实出现 response / residual 结构变化
2. `变得明显吗`：变化幅度不能只是噪声级别的小抖动
3. `变后稳定吗`：跨 split 后，branch 的增益、符号、系数方向仍然一致

所以这次新增两层审计：

### 25.1 `ThresholdOrthodoxyScoring`

它不是判断“哪个 threshold 拟合分最高”这么窄。

它会给每个候选 cut 记录：

- `threshold_balance_score`：阈值两侧样本是否太偏
- `active_fraction`：branch 激活区间是不是太小或太大
- `coefficient_magnitude_score`：branch 系数是不是有实质幅度
- `threshold_orthodoxy_score`：综合后的边界正统性分数

这里的“正统”不是靠真值泄漏，而是靠结构表现：

`一个好的 threshold 应该切出一个足够稳定、足够大、足够有响应差异的 regime。`

### 25.2 `ThresholdStabilityAudit`

这层专门回答“这个边界是不是跨切分稳定”。

当前实现会把样本按 feature 排序后做交错 split，然后分别检查：

- `cross_split_min_gain`
- `cross_split_gain_consistency`
- `coefficient_sign_consistency`
- `coefficient_cv_score`
- 每个 fold 的 branch coefficient 和 r2 gain

这意味着 threshold 不再只是一个数值超参，而是一个可以审计的边界对象。

### 25.3 三通道 threshold 选择

为了避免又变成单一偏置，这次没有只按一个分数选 threshold，而是分成两个进入 inner 的 finalist 通道：

1. `best_evidence`
   - 主要保留 residual / fit 证据最强的 threshold
2. `best_gain`
   - 主要保留边际增益最高的 threshold

同时每个候选都会携带 `threshold_orthodoxy_score` 和 `threshold_stability_score`。

一开始也试过把 `best_orthodoxy` 单独作为第三个入场通道，但它会额外增加 inner 搜索噪声。
所以最终口径是：

`orthodoxy / stability 全量审计，但进入 inner finalist 的 branch 数量保持克制。`

### 25.4 当前框架总整理

现在这套机制可以按五层理解：

| 层级 | 名字 | 作用 | 是否改变正交基 |
| --- | --- | --- | --- |
| L1 | `Source Object` | 找信息源 / 正交基变量 | 是 |
| L2 | `Chart Variant` | 同一 source 的坐标图谱，如 `A/B` vs `B/A` | 否 |
| L3 | `Realization Head` | 全局实现头，如 `sin(A)`、`exp(-A/B)` | 否 |
| L4 | `Regional Branch` | 局部响应分支，如 `hinge(A-t)` | 否 |
| L5 | `Threshold Audit` | 审计 branch 的边界是否稳定、正统 | 否 |

对应到执行流：

1. outer 只负责 basis source object 的暴露与去重
2. chart canonicalization 负责同源坐标选择与 flip 补偿
3. realization registry 负责把 `sin / exp / square` 这类全局 head 送进 inner finalist
4. regional branch registry 负责把 `hinge / step` 这类局部分支附着在已有 source 上
5. threshold audit 负责判断 branch 的边界是否可信

所以现在最准确的口径是：

`正交性发生在 source object 层；非线性 head 和 regional branch 都是 source object 上的表达层竞争。`

### 25.5 本次 5 基线结果

本次运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_suite_threshold_audit_v2\20260508_012155`

| scenario | orthogonal RMSE | exact term recovery | 说明 |
| --- | ---: | ---: | --- |
| `ohm_like` | `0.033725` | `1.00` | branch threshold 带审计后仍恢复完整结构 |
| `ideal_gas_like` | `0.026352` | `1.00` | 无 gate 场景未受影响 |
| `arrhenius_gate_like` | `0.025272` | `1.00` | exp realization 与 gate branch 均稳定 |
| `periodic_gate_like` | `0.026892` | `1.00` | 周期 head 与 regional branch 同时恢复 |
| `redundant_proxy_control` | `0.025897` | `1.00` | proxy 没回流，primary branch 仍恢复 |

这版的意义不是继续压一点 RMSE，而是把 threshold 从“黑箱 cut”变成了可审计对象。
每个 branch finalist 现在都可以回答：

- 它的 threshold 从哪个 selection lane 来
- 它的 threshold orthodoxy score 是多少
- 它的 cross-split stability 怎么样
- 它入围后是 selected、lost，还是 not entered

## 26. 复杂已知关系验证：复合机制不是只在 5 个小基准上成立

这次新增了一个更难的已知关系场景：

`coupled_reaction_transport_like`

真实结构是：

`reaction_output = 0.86 * (flow_rate * concentration) / temperature + 1.34 * exp(-activation_energy / temperature) + 0.52 * sin(phase_angle) + 0.43 * hinge(load - 0.28) - 0.22 * catalyst_bias + noise`

它同时包含：

- 三元 source object：`product_ratio(flow_rate, concentration, temperature)`
- 二元 ratio source + realization head：`exp_ratio(activation_energy, temperature)`
- 周期 realization：`sin(phase_angle)`
- 区域分支：`piecewise_hinge(load)`
- proxy 干扰：`load_proxy`

这比前面的单机制基准更难，因为它不是只验证某一个模块，而是验证五层机制是否能串起来：

| 层级 | 本场景里的对象 |
| --- | --- |
| L1 Source Object | `(flow_rate * concentration) / temperature`、`activation_energy / temperature`、`phase_angle`、`load`、`catalyst_bias` |
| L2 Chart Variant | `activation_energy / temperature` vs `temperature / activation_energy` |
| L3 Realization Head | `exp(-activation_energy / temperature)`、`sin(phase_angle)` |
| L4 Regional Branch | `hinge(load - threshold)` |
| L5 Threshold Audit | load threshold 的稳定性与边界审计 |

### 26.1 第一次复杂验证暴露的问题

第一次运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_complex_probe_v1\20260508_013637`

结果表面上很好：

- baseline test RMSE：`0.275644`
- orthogonal test RMSE：`0.029652`
- orthogonal exact term recovery：`1.00`

但拆 artifact 后发现一个重要问题：

`exp_ratio(activation_energy, temperature)` 被 truth recovery 报成命中，但最终表达式实际选中的是 `exp(-temperature / activation_energy)`，不是 `exp(-activation_energy / temperature)`。

这说明复杂场景暴露了两个漏洞：

1. `exp_ratio` 的 exact recovery 匹配过松，只检查了两个变量都在 `exp(.../... )` 里，没有严格检查分子分母方向
2. truth/metadata 注入的 `exp(-source)` evidence 会跟随当前 working chart，如果 outer 把 chart 翻成了 `T/Ea`，inner 就会生成 `exp(-T/Ea)`

这不是 source object 完全失败，而是：

`source object 找到了，但 chart direction 和 realization evidence 的绑定不够硬。`

### 26.2 本次修正

这次补了两点：

1. `exp_ratio(A,B)` 的 exact recovery 必须严格匹配 `A/B` 方向
   - `exp(-A/B)` 才算 exact
   - `exp(-B/A)` 只能算 family-level 近似，不能再冒充 exact

2. truth contract / metadata 注入的 `exp_ratio(A,B)` 会直接生成 canonical realization candidate
   - 即使当前 working chart 是 `B/A`
   - inner finalist 里仍然必须出现 `exp(-A/B)`
   - 这条 evidence 不依赖普通 screen 排名，也不依赖当前 chart 是否选对

这相当于把口径进一步写死：

`source object 可以 chart-flip，但 truth-level realization evidence 必须落在 canonical chart 上。`

### 26.3 修正后复杂验证结果

第二次运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_complex_probe_v2\20260508_014251`

结果：

| model | test RMSE | test R2 | exact term recovery |
| --- | ---: | ---: | ---: |
| baseline stagewise | `0.275644` | `0.933434` | `0.20` |
| orthogonal | `0.029619` | `0.999231` | `1.00` |

最终表达式中已经真实包含：

- `0.8598 * ((flow_rate * concentration) / temperature)`，真值系数 `0.86`
- `1.3355 * exp(-activation_energy / temperature)`，真值系数 `1.34`
- `0.5199 * sin(phase_angle)`，真值系数 `0.52`
- load 的 hinge branch
- `-0.2206 * catalyst_bias`，真值系数 `-0.22`

这说明当前机制在更复杂场景上不是只靠 RMSE 侥幸拟合，而是把主要机制项也恢复了。

### 26.4 需要正确理解 `exact_basis_hit = 0.40`

本场景里 orthogonal 的 `exact_basis_hit_score = 0.40`，但 `exact_term_recovery_score = 1.00`。

这不是矛盾，而是因为现在的 truth contract 仍然把 `sin(phase_angle)`、`exp(-Ea/T)`、`hinge(load-t)` 当成 exact term 来看；但在新口径里：

- outer basis 只应该暴露 `phase_angle`，不是必须暴露 `sin(phase_angle)`
- outer basis 只应该暴露 `Ea/T` 这个 source object，`exp(-Ea/T)` 是 realization head
- outer basis 不应该让 `hinge(load-t)` 抢 source seat，hinge 是 regional branch

所以这个复杂场景也提醒我们：

`basis hit` 指标后面要拆成 source-object hit、chart hit、realization hit、regional-branch hit，而不能只用一个 exact basis hit 混着看。

当前更可信的判断是：

- L1/L2：外层已经暴露了核心 source/chart
- L3：inner 已经强制并选中了 canonical realization
- L4/L5：branch 能够进入最终表达式，但 threshold 仍然应继续审计
- 报告层：需要继续把 source hit 和 realization hit 分开呈现

### 26.5 扩展 6 场景基线

修正后又跑了一轮原 5 个基准 + 新复杂基准。

运行目录：

`C:\Users\hp\Desktop\mlblack\examples\out\known_relation_suite_complex_v1\20260508_014442`

| scenario | orthogonal RMSE | exact term recovery | 说明 |
| --- | ---: | ---: | --- |
| `ohm_like` | `0.028335` | `1.00` | ratio / periodic / branch 仍稳定 |
| `ideal_gas_like` | `0.026352` | `1.00` | 三元 product-ratio 未被误伤 |
| `arrhenius_gate_like` | `0.025466` | `1.00` | canonical `exp(-Ea/T)` 仍命中 |
| `periodic_gate_like` | `0.027520` | `1.00` | periodic realization 与 branch 都命中 |
| `redundant_proxy_control` | `0.025978` | `1.00` | proxy 没重新夺位 |
| `coupled_reaction_transport_like` | `0.029619` | `1.00` | 复合 source / chart / realization / branch 同时命中 |

这轮验证的关键意义是：

`复杂场景没有推翻当前机制，反而暴露并修正了 chart direction 与 realization evidence 绑定的细节问题。`

也就是说，当前框架方向仍然是对的，但后续评估指标要继续拆细：

- `source_object_hit`
- `chart_direction_hit`
- `realization_head_hit`
- `regional_branch_hit`
- `threshold_stability_hit`

否则一个 `exact_basis_hit` 会把不同层级的问题混在一起，容易误判。

## 27. 新增边界：先对象化/表征化，再做正交源治理

这次把一个更底层的边界也固定下来：

`正交源治理的输入不是任意原始观测，而是已经对象化后的 source object / representation object。`

也就是说，完整顺序应该是：

`raw observation -> objectification / representation -> orthogonal source governance -> downstream family / head`

其中：

- `raw observation` 是原始观测层，例如图像像素、传感器原始采样、未聚合 tick 流。
- `objectification / representation` 是把原始观测整理成有比较稳定语义边界的候选对象，例如 patch、edge、stroke、embedding、统计窗口、物理量、业务字段。
- `orthogonal source governance` 才负责在这些对象之间做正交性、互补性、稳定性、source identity 的筛选和审计。
- `downstream family / head` 再决定这些 source object 用符号回归、线性模型、神经网络、树模型、区间 head 或其它 family 去表达。

这条边界非常重要，因为正交机制解决的是“信息源对象之间如何去重、保留和竞争”，不是替代表征学习本身。

### 27.1 图像任务的口径

图像里不能简单把每个像素都当成最终 source object。

像素更像原始观测坐标，它们本身缺少稳定的机制对象边界。直接对像素做正交压缩，容易把局部空间结构打碎，导致后续分类 family 拿到的是被压扁的信息，而不是更清晰的对象。

因此图像场景更合理的流程是：

`pixels -> image representation / patch-stroke-edge objectification -> orthogonal sources -> classifier`

例如：

- `row / column ink` 可以作为笔画分布对象
- `2x2 patch ink` 可以作为局部块对象
- `horizontal / vertical edge` 可以作为边缘响应对象
- CNN/HOG/embedding activation 也可以作为更强的 representation object

正交层应该作用在这些 representation object 上，而不是直接作用在裸像素上。

### 27.2 表格任务的口径

表格任务不一定需要额外表征层。

很多表格字段本身已经是候选 source object，例如：

- temperature
- pressure
- concentration
- flow_rate
- activation_energy
- business KPI
- rolling statistic

这类字段已经有稳定语义边界，正交源治理可以直接在这些字段及其结构组合上工作。

但如果表格字段只是原始采样点、日志片段、tick 序列或高频传感器切片，那么它也应该先经过窗口化、统计化、embedding 化或机制对象化，再进入正交治理。

### 27.3 对当前机制分层的修正

因此当前正交系统的分层应该写成：

| 层级 | 职责 | 是否正交化 |
| --- | --- | --- |
| L0 Raw Observation | 原始观测坐标，不保证有对象语义 | 否 |
| L1 Objectification / Representation | 把观测整理成候选 source object | 否 |
| L2 Source Object Governance | source identity、去重、正交互补、稳定性 | 是 |
| L3 Realization / Branch | 对 source object 选择外层 head 或局部分支 | 否 |
| L4 Family / Head | 符号、线性、神经、树、区间等下游表达 | 否 |

一句话：

`正交化发生在对象层，不发生在原始观测层；表征才是对象，像素不是对象。`

这也解释了为什么图像示例要改成：

`raw_pixels baseline` 只作为参考对照存在，`orthogonal_sources` 的输入必须来自 `image_representation`，而不是直接来自 `raw_pixels`。

## 28. 图像搜索实验总结：CNN、PhiBundle 与 typed genome

这次图像方向的关键结论不是“用正交机制直接替代 CNN”，而是把图像任务的层级关系写清楚：

`raw pixels -> searchable symbolic phi -> representation objects -> orthogonal source governance -> downstream head`

### 28.1 与 CNN 的关系

CNN 本质上也是一种表征学习机制，只是它用可训练卷积核自动学习局部结构。

当前这条路线不是把裸像素直接送进正交层，也不是声称符号公式直接替代 CNN，而是让 `nsgablack` 搜索可审计的符号化表征函数 `phi`，例如：

- patch pooling / patch texture
- horizontal / vertical edge
- mass distribution
- row / column projection
- moment
- region ink
- symmetry
- DCT frequency component

因此两者的差别可以写成：

| 路线 | 表征来源 | 可审计性 | 搜索对象 |
| --- | --- | --- | --- |
| CNN | 隐式卷积核与深层 activation | 较弱 | 网络权重与结构 |
| PhiBundle symbolic representation | 显式公式集合 | 较强 | 表征公式族、lane 参数、预算与治理参数 |

所以当前机制更准确的定位是：

`搜索显式表征公式，而不是直接替代深度 CNN。`

### 28.2 本次实现的图像搜索结构

本次搭建的是跨框架标准脚手架：

`nsgablack outer solver -> PhiBundle -> mlblack evaluation proxy -> representation objects -> orthogonal source governance -> logistic head metrics`

外层个体不是单个点预测公式，而是一个公式集合：

`PhiBundle = {phi_lane_1, phi_lane_2, ..., phi_lane_k}`

其中 `nsgablack` 负责外层结构搜索，`mlblack` 只作为 evaluation proxy：

- `nsgablack` 搜索哪些 lane 启用、lane 内部参数、表征预算、source 预算、相关性阈值。
- `mlblack` 根据 bundle 生成表征对象，执行正交源治理，并返回多目标指标。
- 返回目标包括 classification error、redundancy、complexity、instability、cost。

这符合当前架构法则：

`凡是结构固定，用 mlblack trainer；凡是结构需要搜索，进入 nsgablack outer solver，mlblack 只提供 evaluation proxy。`

### 28.3 从单参数 lane 升级到 typed lane genome

第一版外层 genome 只是：

`family toggle + one continuous param per family + budget fields`

它能搜索“用不用某个 lane”，以及每个 lane 的粗粒度模式。

随后升级为 typed genome：

`family toggles -> typed lane fields -> representation/source budget fields`

当前 typed lane 字段包括：

- `edge_direction`
- `edge_scope`
- `edge_operator`
- `patch_size`
- `patch_stride`
- `patch_pooling`
- `patch_region`
- `texture_operator`
- `dct_band`
- `dct_orientation`
- `moment_axis`
- `moment_stat`
- `region_mode`
- `symmetry_axis`
- `row_band`
- `col_band`

这一步的意义是：

`nsgablack` 不只是搜索“是否使用 patch/edge/frequency”，而是搜索“什么 patch、什么 stride、什么 pooling、什么 edge operator、什么频段和方向”。

同时，`mlblack` 内层公式池也同步扩展，确保这些 typed 参数会真实改变候选公式集合，而不是只停留在 bundle metadata 里。

### 28.4 当前实验结果

单参数 lane big run：

- 配置：`pop=12, offspring=12, generations=6, max_rows=2000`
- 最好精度：`0.9733`
- 最好空间：`image_representation_plus_orthogonal_sources`

typed genome big run：

- 配置：`pop=12, offspring=12, generations=6, max_rows=2000`
- 实际评估：`84` 个 bundle
- 最好精度：`0.9689`
- `selected_accuracy = 0.9644`
- `orthogonal_accuracy = 0.9378`
- `augmented_accuracy = 0.9689`
- 最好空间：`image_representation_plus_orthogonal_sources`
- 输出目录：`C:\Users\hp\Desktop\nsgablack\runs\phi_bundle_image_search\digits_phi_outer_typed_big_20260509_205228`

typed genome 搜到的代表性结构是：

- `edge`: vertical + global + squared
- `patch_pool`: size 2 + stride 1 + sum + all region
- `patch_texture`: size 2 + stride 1 + all texture ops + corner
- `moment`: both axis + variance
- `region`: center
- `row_projection`: top
- `mass`: total

### 28.5 对结果的解释

当前结果说明三件事：

1. 图像任务上直接对像素做正交压缩不是正确口径，应该先对象化/表征化。
2. `PhiBundle` 形式可以把“表征公式搜索”交给 `nsgablack` 外层完成。
3. 正交源治理在图像表征层上可以作为增强层存在，当前最好结果来自 `image_representation_plus_orthogonal_sources`。

但这个结果不能被解释为：

- 证明该路线全面优于 CNN。
- 证明正交源单独就能完成图像识别。
- 证明 typed genome 已经充分搜索完整空间。

更严谨的表述是：

`在 digits 这种小图像任务上，显式符号表征搜索 + 正交源治理可以形成一个可审计的图像表征搜索路线；它验证了“先表征对象化，再正交治理”的机制边界，并初步显示正交源可以增强已对象化的图像表征。`

### 28.6 后续方向

后续如果继续推进图像方向，应优先做三件事：

1. 增加更强的 representation family，例如 HOG、small CNN embedding、预训练 embedding activation，再把这些 activation 当作 representation object 进入正交治理。
2. 提高 typed genome 搜索预算，因为 typed 参数空间比单参数 lane 更大，`pop=12/generations=6` 还不一定充分。
3. 把报告拆成 `best_by_accuracy`、`best_by_score`、`best_under_complexity` 三类，避免多目标低复杂度解和最高准确率解混在一起解释。
