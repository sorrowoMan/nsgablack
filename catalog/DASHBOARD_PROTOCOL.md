# Dashboard Protocol

这份协议用于约束 `nsgablack` 与 `mlblack` 的 catalog dashboard。
目标不是强行共享所有页面代码，而是共享同一套：

- 查询面契约
- URL / session 状态契约
- 交互语义契约
- 回归验证清单

这样两边即使 kind / field 模型不同，也能长期保持同一层产品语义。

## 1. 产品目标

catalog dashboard 不是示例脚本，而是正式查询页。
最小产品语义：

- 左侧：facet filters
- 中间：可点击的组件索引，默认显示名称和简短用途；完整表格为高级浏览方式
- 右侧：用法 / 接口 / 关系 / 来源四个详情页签
- 顶部：紧凑标题、query 与搜索范围，常用意图快捷入口；首屏即可看到结果和详情。
- 侧栏：profile、kind 与字段筛选；排序、列方案、显示数量及折叠偏好收进“显示设置”。
- 本地 scope / Project / DB 控件收进“数据源与项目”；hosted 模式不渲染不可用控件。
- `primary` / `secondary` 保留稳定 DOM 标识与状态语义，不要求占用两排顶层表单。
- URL：可 deep-link 到当前页面状态

## 2. 查询层契约

UI 层只依赖下列统一查询面：

- `catalog_source_info(...)`
- `catalog_summary(...)`
- `catalog_schema(...)`
- `list_entries(...)`
- `search_entries(...)`
- `show_entry(...)`
- `catalog_neighbors(...)`
- `catalog_facets(...)`
- `catalog_ui_snapshot(...)`

不应把 registry / DB / project loader 细节散落进页面代码。

### 2.1 当前架构的装配说明字段

条目通过既有 `CatalogEntry.contract.catalog` 声明 `role/concepts/operations/boundaries`。
`role` 为非空字符串，后三项为非空字符串组成的列表；不增建独立目录或运行时协议。
查询/详情/导出应使用同一个 guidance 解释，未声明 role 的条目回退原 kind。

- kind 保留兼容分类；例如 Unit builder 仍可为 representation，但 role 为 unit_builder。
- concepts 表达用户意图；operations 表达已有方法、属性或装配操作，不混入 config_keys。
- boundaries 必须显示当前不支持的组合，不能把占位偏好当成完整算法。
- companions 可导航到所属 Adapter 与可替换部件；它不表示必须同时启用所有相关实现。
- wiring_status/wiring_notes 必须区分说明、模板、签名检查和不可核对；签名检查不是运行验收。
- 用法页先说明装配位置、输入前提和外部对象来源，再展示可复制代码与具体接入/检查步骤；详细参数、来源与验证记录默认折叠。专门教学段优先展示，完整Project收据仍可展开。泛化语句不能当成操作说明，缺少具体前提/结果检查时须明确显示缺口。接口页保留方法、配置、契约、整理说明及原始声明。
- 教学验收不能只检查字段非空：必须有具体使用目的、装入后实际发生的流程、调用者/输入来源、与正式Case一致的代码和结果读法。组合器要明确提案归属、反馈回传、状态是否共享，以及它与串行精修的差别；仅有构造与挂载两行代码仍是片段。
- 不渲染空列表标记、空详情面板；已有Markdown列表不二次包编号。已有有效专属章节时，不再附加同版本整本文档开头的通用引用；不同Project、版本与运行收据仍保留。
- 数据库AI教程包含具体场景、准备、文件落点、代码、执行过程、结果读法和有代码的变化用法，绑定源码、生成及独立源码复核版本；实际接线、消费者和变体被另一次复核否决时不得发布。没有完整人工基础教程时优先展示有效AI教程；已有完整人工教程时保留基础示例，AI提供变化用法。过期/无效说明不能遮住现有来源。代码仅展示，浏览不调用模型、不执行代码。文档基础用法有多个代码块时必须全部显示，变体独立折叠，不把第二步挂载代码藏进源码。
- 关系页优先显示显式配套与真实用法调用，支持双向跳转至目标用法并返回。用法关系须有源码位置证据；同现不代表强制依赖或兼容承诺。共享context/artifact/phase契约只按已发布声明匹配，不按名字猜边。ML声明由所属registry规范投影，保留原始contract；default/core及数据库/源码两路使用同一解释。
- 快捷意图查询清空旧字段筛选及对应 URL；上一项/下一项保持当前分类，关系跳转仍允许跨分类。
- 列表查询不截断为固定 250 条；显示窗口由 page_size 控制，并可用“显示更多组件”扩大。列表和高级表格只在真实选择事件更新 selected，不能用旧位置覆盖导航。空结果保留已有详情；显式清除后不自动重新选中首项。

default/framework-core 继续使用既有统一过滤，不因说明字段改变主干口径。
完整中文说明见 `docs/architecture/CATALOG_USAGE_CN.md`。上述字段是可发现性说明，不授予池写入、全局资源或算法决策权限。

## 3. URL 契约

### 3.1 核心参数

所有 dashboard 都应支持下列 query params：

- `profile`
- `scope`
- `kind`
- `query`
- `selected`
- `sort_by`
- `sort_dir`
- `detail_tab`
- `open_relations`
- `column_mode`
- `page_size`
- `results_collapse`

### 3.2 scope 扩展参数

按需要支持：

- `project_path`
- `include_global`

### 3.3 framework 可选扩展参数

不同框架可增加自己的公共参数，但必须保持含义稳定：

- `field`：例如 `nsgablack` 的搜索范围
- `db_path`：例如 `mlblack` 的 SQL catalog 连接目标
- `source_mode`：例如 `mlblack` 的 registry / DB 读取模式

### 3.4 facet filters

facet filters 统一序列化为：

- `f_<field>=value1,value2`

例如：

- `f_tags=local_search,demo`
- `f_family=neural`

### 3.5 参数取值约束

- `sort_by`: `default | title | key | kind`
- `sort_dir`: `asc | desc`
- `detail_tab`: `overview | interface | relations | source`；原 `overview` 深链继续表示“用法”
- `open_relations`: 逗号分隔的 relation group 名称
- `column_mode`: `compact | standard | full`
- `page_size`: 正整数
- `results_collapse`: `expanded | collapsed`

### 3.6 URL 规则

- deep-link 必须恢复“筛选条件 + 排序 + 当前 tab + 展开 relation 分组 + 选中项 + 结果表格状态”
- `selected=__none__` 这类内部哨兵值不应写进 URL
- 没有值的参数应省略，不应写空字符串噪音

### 3.7 CLI 初始状态

`python -m ... catalog ui` 的正式入口也必须能注入结果区初始状态：

- `--column-mode`
- `--page-size`
- `--results-collapse`

要求：

- CLI 传入的初始值必须在首屏 UI 生效
- 若 URL 同时提供对应 query params，URL 优先级高于 CLI 默认值
- CLI 与 URL 的字段名语义必须保持一致

## 4. Session State 契约

### 4.1 核心页面状态

建议统一使用这些 key：

- `catalog_ui_profile`
- `catalog_ui_scope`
- `catalog_ui_kind`
- `catalog_ui_query`
- `catalog_ui_selected`
- `catalog_ui_project_path`
- `catalog_ui_include_global`

### 4.2 facet state

facet filters 使用：

- `catalog_ui::facet::<scope>::<kind>::<field>`

### 4.3 view state

可交互视图状态使用：

- `catalog_ui::view::<scope>::<kind>::sort_by`
- `catalog_ui::view::<scope>::<kind>::sort_dir`
- `catalog_ui::view::<scope>::<kind>::detail_tab`
- `catalog_ui::view::<scope>::<kind>::open_relations`
- `catalog_ui::view::<scope>::<kind>::column_mode`
- `catalog_ui::view::<scope>::<kind>::page_size`
- `catalog_ui::view::<scope>::<kind>::results_collapse`

### 4.4 navigation state

跳转栈使用：

- `catalog_ui_navigation_stack`

## 5. 交互语义契约

### 5.1 组件索引

默认使用原生单选列表，支持键盘与长名称折行。`standard` 显示名称和最多两行用途，`compact` 仅显示名称，`full` 保留完整字段表格。宽屏索引约310px，详情使用剩余宽度；窄屏堆叠并限制列表高度。

要求：

- 单击组件行即可选中
- 选中项联动右侧 detail
- deep-link 能恢复当前选中项
- 当前列显示方案必须是正式状态
- 当前 page size 必须是正式状态
- 当前结果折叠方式必须是正式状态

### 5.2 结果展示状态

结果区的展示方式必须可序列化、可恢复。

要求：

- `column_mode` 必须进入 URL，并能从 URL 恢复
- `page_size` 必须进入 URL，并能从 URL 恢复
- `results_collapse` 必须进入 URL，并能从 URL 恢复
- `page_size` 表示当前结果表格的可见窗口大小，而不是后台查询上限
- 复制 deep-link 后重新打开，结果区的列方案、显示条数、折叠状态必须完全回位

### 5.3 排序

排序是正式状态，不是前端偶发行为。

要求：

- 当前排序必须进入 URL
- 当前排序必须能从 URL 恢复
- `default` 表示保留 catalog 原始顺序

### 5.4 Detail Tabs

右侧 detail 拆成四段稳定语义：

- `overview`：用法
- `interface`：接口与装配声明
- `relations`
- `source`

要求：

- 当前 tab 必须进入 URL
- 当前 tab 必须能从 URL 恢复
- 页签及显示设置使用稳定控件身份；交互回调须在下一次URL恢复前同步新选择，支持反复切回原值，不能由旧查询参数覆盖本次操作。

### 5.5 Relation Groups

relation group 的展开状态必须是显式状态。

要求：

- 页面必须有可序列化的 relation group 选择面
- 展开状态必须进入 URL
- 展开状态必须能从 URL 恢复

### 5.6 Hidden Selection

若当前选中项被筛选隐藏：

- 不应立即丢失选中态
- 右侧仍应能展示详情
- 页面应明确提示“当前选中项已被筛选隐藏”
- 应提供“显示它”或“清除选中”动作

### 5.7 Control Layout Protocol

顶部控件区不是随手摆的 `st.columns(...)`，而是正式协议的一部分。

要求：

- 页面必须稳定存在 `primary` / `secondary` 两排 control row
- control row id 必须稳定，可供 E2E 与样式协议复用
- control slot 的列宽、label、placeholder、caption、help 骨架必须长期对齐
- 框架可以有各自字段，但不应破坏“第一排主查询、第二排数据源 / 项目 / 补充控制”的布局语义

### 5.8 Button / Rerun Semantics

交互按钮默认应走 callback 改状态，而不是“按钮分支里再显式手动 rerun”。

要求：

- 选中切换、关系跳转、跳转栈返回、清空筛选这类动作优先使用 `on_click`
- 除非确实需要二段状态推进，否则不要在按钮分支里额外调用 `rerun`
- query trace 回归中，一次“上一项 / 下一项”切换应只保留必要 miss
- 当前基线预算：单次选中切换的 loader delta 应控制在 `<= 8`

### 5.7 Relation Jump

从 relation 区跳转时：

- 必须更新 `selected`
- 必须更新跳转栈
- 必须更新 URL

## 6. 回归要求

每次改 dashboard，至少验证：

- framework scope list/search/show
- project scope list/search/show
- deep-link 基础参数恢复
- facet filter 参数恢复
- sort / tab / relation-group / result-layout 参数恢复
- deep-link roundtrip 后 UI snapshot 状态一致
- table selection helper
- hidden selection 行为
- dashboard script import mode

## 7. 框架自由度

协议层允许不同框架保留自己的 kind / field 体系：

- `mlblack`: `family / preset / head / component / provider / plugin`
- `nsgablack`: `adapter / plugin / bias / representation / suite / tool / doc / example`

但它们必须共享同一层 dashboard protocol，而不是长成两套完全不同的产品语义。
