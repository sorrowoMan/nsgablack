# NSGABlack 简历型技术栈亮点（中文，含复杂度证明）

定位：给老师/面试官“30 秒扫一眼就懂”的技术栈清单。每条都附：
- `证据`：能在仓库里直接定位到的实现路径
- `复杂度证明`：为什么难、常见坑、我怎么规避

## 1) 架构与设计模式（可解释、可扩展、可维护）

- 分层与边界：Core 稳定底座 + Wiring 装配层 + Plugin 生态层（core 不装配，wiring 做权威装配）
  - 证据：`core/`、`utils/wiring/`、`plugins/`
  - 复杂度证明：难点是“扩展点多但依赖方向不混乱”；我把装配收敛进 wiring，让 core 长期稳定，避免新需求把 solver 变成胶水堆。
- 插件化生命周期（事件分发）：统一 hook（init/pop/gen/finish），支持 priority 调度与可选 short-circuit
  - 证据：`plugins/base.py`
  - 复杂度证明：常见坑是 hook 顺序不一致/返回值悄悄失效/插件互相踩踏；我用统一契约 + priority +（可选）短路规则把行为边界固定。
- Adapter/Strategy：把“搜索策略/控制器/多智能体协调”从 solver 解耦，允许多策略组合与替换
  - 证据：`core/algorithm_adapter.py`、`core/role_adapters.py`
  - 复杂度证明：难点是“组合后谁负责控制流、状态如何共享”；我让 adapter 成为一级公民，solver 只提供稳定生命周期与最小约束。
- Pipeline：把表示/修复/变换做成可插拔管线（避免业务逻辑塞进 evaluate）
  - 证据：`representation/`、`utils/representation/`
  - 复杂度证明：常见坑是修复逻辑散落在 solver/问题定义里，复用困难；我把变换/修复收敛为 pipeline 组件，做到可插拔、可审计。
- Factory（并行工程）：`problem_factory` 支持子进程内构造 problem，避免跨进程传不可序列化对象
  - 证据：`utils/parallel/evaluator.py`
  - 复杂度证明：Windows 多进程的典型坑是 pickling 失败/首轮极慢；我提供 factory + picklable 预检 + fallback，保证“能并行就并行，不能就退回还能跑”。

## 2) 信息传递与工程通信机制（低侵入、可审计）

- Context 机制：跨模块信息用 `dict` 传递，并定义“最小可序列化 schema”（并行/串行共用）
  - 证据：`core/state/context_schema.py`
  - 复杂度证明：难点是“信息要够用但不能把不可序列化大对象塞进来”；我用 minimal schema 保障并行可用，同时允许 extra 扩展。
- Context Key 约定：统一 key 命名与语义，降低协作成本，减少“隐性协议”
  - 证据：`core/state/context_keys.py`
  - 复杂度证明：常见坑是同一语义不同 key（口径无法对齐）；我把协议显式化为 keys，让新增模块可对齐。
- 显式构造注入 + wiring 装配：不引入重型 DI 容器/事件总线，降低副作用与排障复杂度
  - 证据：`utils/wiring/`、`core/`
  - 复杂度证明：DI/总线容易让故障定位变难；我选择“明确调用链 + 显式装配”，复杂度可控。

## 3) 并行与性能工程（可控、可切换、有护栏）

- 评估并行化：线程/进程后端可切换，面向黑箱评估（evaluate + constraints + bias）提速
  - 证据：`utils/parallel/evaluator.py`
  - 复杂度证明：难点是黑箱评估不纯/耗时差异大；我把并行限定在“评估层”，并提供负载均衡与异常隔离。
- 工程护栏：picklable 预检、strict/fallback、重试策略、chunk 粒度、负载均衡选项
  - 证据：`utils/parallel/evaluator.py`
  - 复杂度证明：常见坑是并行跑到一半才炸；我把“炸的方式”参数化（strict/fallback/retry），行为可预测。
- 无侵入集成：`with_parallel_evaluation(...)` 装饰式集成，不改 solver 基类，只 override `evaluate_population`
  - 证据：`utils/parallel/integration.py`
  - 复杂度证明：难点是“并行要通用但不能污染核心”；我用 wrapper 方式按需启用，core 保持稳定。

## 4) 可复现、可追溯、可审计（实验口径 + 模块贡献）

- 统一实验口径：逐代 CSV + summary JSON（seed/time/eval_count/best_score 等），便于横向对比
  - 证据：`plugins/ops/benchmark_harness.py`
  - 复杂度证明：常见坑是每个脚本各写一套记录导致口径不一致；我把口径固化成插件，算法只管搜索。
- 模块贡献报告：modules.json + bias.json（可选 bias.md），并记录插件 hook 耗时 profile
  - 证据：`plugins/ops/module_report.py`、`plugins/base.py`
  - 复杂度证明：难点是“组合多了说不清谁贡献了什么”；我把启用模块、偏置统计、插件耗时统一落盘，变成可审计证据。
- 插件 profiling：PluginManager 自动统计每个 hook 的耗时（total + per-event），支持定位瓶颈
  - 证据：`plugins/base.py`
  - 复杂度证明：性能问题常被误判成“抽象层开销”；我用 hook 级 profile 把瓶颈定位到模块级。

## 5) 配置、日志与落盘（工程化跑实验）

- 配置加载：JSON/TOML/YAML，支持 deep merge、unknown keys 检测、dataclass 注入（可 strict）
  - 证据：`utils/engineering/config_loader.py`
  - 复杂度证明：难点是配置漂移与拼写错误被静默忽略；我提供 unknown keys 检测与 strict 模式，避免错配悄悄生效。
- 日志配置：统一 logger 配置，支持 JSON 输出与文件落盘（便于批量实验解析）
  - 证据：`utils/engineering/logging_config.py`
  - 复杂度证明：常见坑是日志格式不统一难以汇总；我提供 json_format，让日志可机器读取。
- 轻量实验追踪：结构化落盘（pareto.csv/config.json/history.json），并处理 numpy JSON 序列化
  - 证据：`utils/engineering/experiment.py`
  - 复杂度证明：难点是 history 里混入 numpy 类型导致 JSON 直接炸；我做递归序列化，保证落盘稳定。

## 6) 依赖治理与可选能力（装得上，也跑得动）

- 可选依赖管理：安全导入封装 + feature 级依赖探测（viz/parallel/ml/acceleration 等）
  - 证据：`utils/runtime/imports.py`
  - 复杂度证明：常见坑是可选依赖缺失导致核心也不可用；我用 safe_import 把增强能力与核心路径隔离。
- 显式依赖声明：核心依赖与 optional extras 分离（visualization/parallel/bayesian/distributed/dev）
  - 证据：`pyproject.toml`
  - 复杂度证明：难点是“依赖越加越重导致安装成本爆炸”；我用 extras 把重依赖变成可选特性。

## 7) 可发现性（Catalog：官方推荐入口索引）

- 显式注册的 Catalog：稳定、可控、避免扫描导入副作用；支持 search/list/show
  - 证据：`catalog/registry.py`、`__main__.py`
  - 复杂度证明：常见坑是扫描 import 触发副作用/可选依赖缺失直接炸；我用显式 registry + lazy load 保证 catalog 本身可靠。

## 8) 质量保障（测试与规范）

- pytest 覆盖关键工程能力：插件/并行/约束/context/catalog/adapter/wiring 等
  - 证据：`tests/`
  - 复杂度证明：组合爆炸会带来高回归风险；我用测试把契约固化，保证架构演进不崩。
- 工具链集中配置：black/mypy/pytest/cov 统一在 pyproject，便于持续迭代
  - 证据：`pyproject.toml`
  - 复杂度证明：规范分散会抬高协作成本；我把配置集中在一个地方，降低维护成本。

## 9) 一句话讲法（对外表达模板）

- “我把优化算法拆成 Core（稳定底座）+ Wiring（权威装配）+ Plugin（工程生态），新点子落地不牵一发动全身。”
- “我做了统一实验口径与模块贡献审计：每次 run 都能追溯启用了什么模块、偏置贡献多少、插件耗时多少。”
- “我把最慢的黑箱评估做成可切换的线程/进程并行，并加了 picklable 预检与 fallback 护栏，真实业务环境下也不容易炸。”

