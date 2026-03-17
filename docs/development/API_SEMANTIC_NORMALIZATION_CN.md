# API 语义归一化规范（全框架）

> 适用范围：`core/`、`adapters/`、`representation/`、`plugins/`、`bias/` 及其公开 API。  
> 目标：解决“同一逻辑多种命名”的认知负担，建立可迁移、可审查、可自动化检查的统一语义体系。

---

## 1. 背景与问题定义

当前框架存在以下高频问题：

- 同一行为在不同模块命名不一致（如 `switch/router/strategy/controller` 混用）。
- 同一动词承载多种语义（如 `resolve` 既用于“读取”，又用于“推断/合并”）。
- 参数词汇不统一（如 `key/selector/route_key` 指向同一语义）。
- 层级职责表达不稳定（如 `ControllerAdapter` 这类双角色后缀增加理解负担）。

这会直接导致：

- 新成员上手慢；
- 跨模块调用成本高；
- 文档与代码语义漂移；
- API 设计评审难以对齐。

---

## 2. 归一化目标（Definition of Done）

当满足以下条件时，视为“语义归一化完成”：

1. **同语义同命名**：同一语义动作在全框架统一动词（允许旧名别名过渡）。
2. **同职责同后缀**：类型后缀只表达一种角色（`Adapter/Plugin/Orchestrator/...`）。
3. **参数词汇统一**：跨组件对同语义使用同参数名（如 `selector/routes/chain/fallback/strict`）。
4. **层边界清晰**：编排逻辑留在 `representation`，算法逻辑在 `adapter`，能力增强在 `plugin`。
5. **可治理**：新增 API 必须通过本规范的审查清单。

---

## 3. 统一语义字典（核心）

### 3.1 动词语义字典（Canonical Verbs）

| 语义 | 统一动词 | 不推荐动词 | 说明 |
|---|---|---|---|
| 获取已有状态/值 | `get_*` | `resolve_*`(读取场景) | `resolve_*` 仅保留“求解/推断”语义 |
| 设置显式状态 | `set_*` | `configure_*`(单值场景) | 单字段赋值优先 `set_*` |
| 构建新对象 | `create_*` | `build_*`(公开 API) | `build_*` 可用于内部组装 |
| 注册能力/组件 | `register_*` | `add_*`(语义不明) | `add_*` 仅用于容器追加语义 |
| 启用/禁用 | `enable_*` / `disable_*` | `set_enable_*` | 禁止“双动词”命名 |
| 串行编排 | `chain_*` | `serial_*`(新 API) | `serial_*` 作为兼容别名 |
| 单路选择 | `select_*` | `switch_*`(非状态机场景) | 避免与状态机“切换”混淆 |
| 路由分发 | `dispatch_*` | `router_*`(方法名) | 类型可保留 `Router`，方法统一 `dispatch_*` |
| 候选生成 | `propose` | `generate_candidates`(Adapter 公共面) | Adapter 公共最小契约保持 `propose/update` |
| 结果反馈 | `update` | `commit_result`(Adapter 公共面) | Adapter 统一更新入口 |

### 3.2 名词/后缀字典（Canonical Nouns / Suffix）

| 角色 | 统一后缀 | 不推荐后缀组合 | 说明 |
|---|---|---|---|
| 算法策略单元 | `Adapter` | `ControllerAdapter` | 控制语义由 orchestrator/selector 表达 |
| 能力扩展单元 | `Plugin` | `ProviderPlugin`（若非 provider 语义） | 仅在 provider 语义明确时使用 `Provider` |
| 表示层编排器 | `Orchestrator` | `Controller`（表示层） | 表示层统一使用 `Orchestrator` |
| 路由器 | `Router` | `Switch`（非状态机） | `Switch` 仅保留状态机语义 |
| 配置对象 | `Config` | `Options`（同层混用） | 全局统一 `Config` |
| 提供器 | `Provider` | `Builder`（对外 API） | `Builder` 保留内部构建语义 |

---

## 4. 分层语义契约（按架构四轴）

### 4.1 Solver（控制平面）

- 负责生命周期与编排入口，不承载算法细节。
- 对外语义：
	- 生命周期：`setup/step/teardown/run`
	- 状态访问：`get_* / set_*`
	- 插件管理：`register_* / unregister_*`
- 禁止：把 representation 路由策略塞进 `SolverBase`。

### 4.2 Adapter（搜索策略）

- 统一公共契约：`propose(...)` / `update(...)`。
- 可选状态契约：`get_state/set_state`。
- 人群向 API 禁止再扩散 `plan/search/explore_step` 等同义入口。

### 4.3 Representation（编码与变异修复）

- 编排语义统一四模式：
	- `chain`（串行）
	- `select`（按索引/条件单选）
	- `dispatch`（按 key 路由）
	- `dynamic`（按 generation/stage 动态）
- 推荐统一入口：
	- `orchestrate_mutation(...)`
	- `orchestrate_repair(...)`

### 4.4 Plugin（能力层）

- 仅做能力增强，不重写算法语义。
- 评估接管语义需显式标注 `provider`，避免混淆到普通插件命名。

---

## 5. 参数命名归一化

| 语义 | 统一参数名 | 历史别名（兼容期） |
|---|---|---|
| 选择依据 | `selector` | `key`, `switch_key`, `route_key` |
| 路由表 | `routes` | `router`, `route_map`, `strategies` |
| 串行链 | `chain` | `pipeline`, `stages`, `steps` |
| 回退策略 | `fallback` | `default`, `default_strategy` |
| 严格模式 | `strict` | `raise_on_missing` |
| 运行阶段 | `phase` | `stage`（若非编排 stage） |
| 代数 | `generation` | `gen`, `iter` |

规则：公开 API 只保留统一参数名；历史别名通过兼容层映射并输出弃用告警。

---

## 6. 现有高频分歧映射（Old -> Canonical）

> 说明：以下是“可讨论+可执行”的归一化映射，优先级建议见第 8 节。

| 位置 | 当前命名 | 建议统一命名 | 语义理由 |
|---|---|---|---|
| `representation/context_mutators.py` | `ContextSwitchMutator` | `ContextSelectMutator` | 这是“选择”，非状态机切换 |
| `representation/context_mutators.py` | `ContextRouterMutator` | `ContextDispatchMutator` | 与分发语义对齐 |
| `adapters/serial_strategy/adapter.py` | `SerialStrategyControllerAdapter` | `StrategyChainAdapter` | 去双角色后缀，突出“串行策略” |
| `adapters/multi_strategy/adapter.py` | `MultiStrategyControllerAdapter` | `StrategyRouterAdapter` | 语义是路由，不是 controller |
| `adapters/role_adapters/adapter.py` | `MultiRoleControllerAdapter` | `RoleRouterAdapter` | 与多策略同构 |
| `core/blank_solver.py` | `set_enable_bias` | `set_bias_enabled` | 去双动词，语义清晰 |
| `core/blank_solver.py` | `resolve_best_snapshot` | `get_best_snapshot` | 明确“读取”语义 |
| `plugins/evaluation/*` | `build_provider` | `create_provider` | 公开 API 动词统一 |

---

## 7. 命名禁忌（Hard Rules）

1. 禁止 `set_enable_*`、`set_disable_*` 这类双动词命名。
2. 禁止在公开 API 中将 `resolve_*` 用于“读取”语义。
3. 禁止 `ControllerAdapter` 这类复合角色后缀。
4. 禁止同层同义多词并存（如同层同时存在 `switch/select/router` 且语义重叠）。
5. 禁止新增公开参数同义词（除兼容期别名）。

---

## 8. 迁移策略（兼容优先）

### 8.1 三阶段迁移

- **阶段 A（vNext）**：
	- 新增 Canonical API；
	- 旧 API 保留为别名；
	- 运行期发 `DeprecationWarning`（含替代名与计划移除版本）。

- **阶段 B（vNext+1）**：
	- 文档、示例、脚手架全部切换到新命名；
	- CI 增加旧 API 使用告警（不阻断）。

- **阶段 C（vNext+2）**：
	- 移除旧 API 别名；
	- 保留迁移指南与 CHANGELOG 对照。

### 8.2 兼容层约定

- 旧方法仅做薄包装，不引入新行为。
- 警告格式统一：
	- `Deprecated: <old_name> -> use <new_name>, removal in <version>`
- 别名生命周期最长不超过 2 个 minor 版本。

### 8.3 一次性统一的执行方案（无兼容层）

> 适用场景：版本尚未稳定、外部用户面较小，或团队明确接受一次性破坏式重命名。

#### 步骤 1：冻结规范

- 以本文作为**唯一命名标准**。
- 最终确定 Canonical 名称，不再保留旧名。
- 对所有存在争议的命名先完成评审，再进入代码改动阶段。

#### 步骤 2：全量替换（代码 + 文档 + 示例 + 测试）

- 全局重命名类名、方法名、参数名。
- 同步更新所有引用位置：
	- 代码实现
	- 对外导出
	- 文档
	- 示例
	- 测试
- 执行方式采用：
	- 全量搜索替换
	- 手动校正语义冲突点
	- 针对公开入口逐一复核

#### 步骤 3：统一检查

- 运行测试，确认功能未因命名替换而失效。
- 全局搜索旧名，确认旧命名“清零”。
- 复核对外文档，确保不再出现旧术语。

#### 执行要求

- 一次性统一期间，不新增兼容别名。
- PR/提交范围必须覆盖“代码 + 文档 + 示例 + 测试”，不能只改其中一部分。
- 所有公开入口必须同步更新，避免内部已改、外部文档仍旧名的语义漂移。
- 合并前必须完成一次“旧名清零”检索确认。

---

## 9. 治理流程（新增 API 必走）

每个新增公共 API 在合并前必须回答：

1. 该 API 对应的 Canonical 动词是什么？
2. 是否和现有 API 语义重复？
3. 参数名是否命中统一词表？
4. 后缀是否符合角色字典？
5. 是否需要兼容别名？若需要，移除版本是多少？

建议将该检查加入 `project doctor` 规则（命名语义检查项）。

---

## 10. 审查清单（评审可直接打勾）

- [ ] 方法动词符合第 3 节字典
- [ ] 类后缀符合第 3 节字典
- [ ] 参数命名符合第 5 节词表
- [ ] 无双动词命名
- [ ] 无跨层语义泄漏（Solver/Adapter/Representation/Plugin）
- [ ] 提供迁移说明（若改公共 API）
- [ ] 提供最小示例或测试覆盖

---

## 11. 推荐落地顺序（低风险优先）

1. **先统一方法别名层**：`set_enable_bias`、`resolve_best_snapshot` 等。
2. **再统一 representation 编排命名**：`switch/router/serial` -> `select/dispatch/chain`。
3. **最后统一 adapter 类型后缀**：`*ControllerAdapter` 收敛为 `*RouterAdapter/*ChainAdapter`。

这样可以在不破坏运行语义的前提下，逐步降低认知噪音。

---

## 12. 与现有文档关系

- 本文是“**语义规范**”（why + what）。
- `docs/development/API_PUBLIC_SURFACE.md` 是“**现状清单**”（where）。
- 建议联动使用：先看现状，再按本文做归一化与迁移排期。

---

## 13. 全框架命名覆盖矩阵

> 这里的“覆盖”指：**本文提出的命名逻辑，是否已经足以解释并约束该目录的公开语义**，不是指“该目录已经全部改名完成”。

| 目录 | 覆盖状态 | 判断 | 代表证据 |
|---|---|---|---|
| `core/` | 已覆盖 | 控制平面公开动作已可稳定收敛到 `get/set/register/enable/disable/select` 语义，主要分歧点已被本文点名。 | `set_enable_bias`、`resolve_best_snapshot`、`select_best`、`resolve_order_strict` |
| `adapters/` | 已覆盖 | Adapter 最小契约 `propose/update` 已稳定；剩余问题主要是类型命名仍有历史包袱。 | `SerialStrategyControllerAdapter`、`MultiStrategyControllerAdapter`、`MultiRoleControllerAdapter`、`resolve_config` |
| `representation/` | 已覆盖 | 表示层已明确落到 `chain/select/dispatch/dynamic` 四类编排语义，本文已能完整解释其命名收敛方向。 | `ContextSwitchMutator`、`ContextRouterMutator`、`PipelineOrchestrator` |
| `plugins/` | 部分覆盖 | Plugin 公共面已能用 `Plugin/Provider/create_*` 约束，但 runtime/system/storage 内部仍有大量 `resolve_*` 与真实 `switch` 状态机语义需要细分。 | `build_provider`、`resolve_population_snapshot`、`dynamic_switch.py`、`_resolve_checkpoint_path` |
| `bias/` | 部分覆盖 | Bias 层已部分自然使用 `select_*`，但偏置选择、阶段调度、快照拼装等术语还缺少 bias 专属子词表。 | `_select_phase`、`_select_top_biases`、`_resolve_biases`、`_resolve_snapshot_payload` |
| `utils/` | 不应强行统一 | 该层大量是内部工具、UI 事件、并行分析、状态机与装配辅助；很多 `switch/select/serial/resolve` 是真实技术语义，不是公开 API 噪音。 | `utils/dynamic/switch.py`、`select_section`、`serial_fraction`、`_on_select_row` |
| `project/` | 部分覆盖 | `project doctor` 需要理解主框架 Canonical API，但其规则实现与导入解析仍属于工具内部逻辑，不宜机械套用公开 API 命名。 | `_resolve_import_path`、`resolve_order_strict`、规则文案中的 `set_enable_bias` |
| `examples/` | 未覆盖 | 示例层目前主要承载历史 API 用法与业务脚本命名，尚未形成“示例命名子规范”，应在核心 API 冻结后集中迁移。 | `solver.set_enable_bias(...)`、`plugin.build_provider()`、`MultiStrategyControllerAdapter`、大量 `_resolve_*` 业务 helper |

### 13.1 分类解释

- **已覆盖**：本文现有词表和边界规则，已经足以指导该目录的公开命名统一工作。
- **部分覆盖**：已有主规则，但还缺目录专属术语细化，不能直接做机械重命名。
- **未覆盖**：当前规范对该目录只给出上位原则，尚不足以直接落地为系统改名方案。
- **不应强行统一**：该目录主要是内部实现、工具语义或技术术语聚集区，不应套用公开 API 归一化规则做一刀切替换。

### 13.2 当前最稳的统一边界

如果现在就要推进一次性命名统一，最稳妥的边界是：

1. 先统一 `core/`、`adapters/`、`representation/` 的公开 API；
2. 再收敛 `plugins/` 中真正对外暴露的 provider / snapshot / runtime 接口；
3. 暂不对 `utils/` 做全局词法统一，只处理确实外溢到公开面的名称；
4. `examples/` 最后统一，因为它本质上是迁移结果的展示层，而不是规范源头。

### 13.3 这份矩阵回答了什么

这份矩阵的含义不是“本文已经 100% 覆盖全仓库所有命名”，而是：

- 对主框架公开面（`core/adapters/representation`），覆盖已经足够强，可以进入执行层；
- 对扩展与外围层（`plugins/bias/project`），覆盖是有方向但未闭环；
- 对工具与示例层（`utils/examples`），不能按同一把尺子机械处理。

因此，若问题是“当前命名逻辑是否已经覆盖全框架”，更准确的答案是：

- **主框架核心面：是，基本覆盖；**
- **扩展与治理面：部分覆盖；**
- **工具与示例面：不能算已覆盖，更不应强推一刀切统一。**
