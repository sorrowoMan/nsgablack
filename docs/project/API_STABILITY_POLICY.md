# API_STABILITY_POLICY（对外 API 稳定性承诺）

本文件给出 NSGABlack 对外 API 的稳定性承诺与弃用策略，用于：
- 让使用者知道“哪些东西可以放心依赖”
- 让维护者在演进架构时有明确边界，避免无意破坏用户代码

本文件与 `docs/CORE_STABILITY.md` 一致：`wiring + plugin + adapter + representation + bias` 是主路径；历史 `deprecated/legacy/` 内容已从仓库清理（如需追溯请查看 git 历史），不做稳定性承诺。

## 1. API 分级

### 1.1 Stable（稳定）

满足以下任一条件，视为 Stable：
- 在 `catalog/registry.py` 中作为“权威推荐入口”出现的条目（尤其是 `plugin.*` / `adapter.*`）
- 在 `docs/CORE_STABILITY.md` 中列为 core promise 的能力层/装配层
- 明确写入本文件的稳定入口

Stable 的含义：
- 在同一主版本号（SemVer 的 MAJOR）内，避免破坏性变更
- 如需变更，必须先走弃用流程（见第 3 节）

当前 Stable 入口（原则：小而稳）：
- `python -m nsgablack catalog ...`（可发现性）
- `nsgablack.catalog` 的查询 API（`get_catalog/search/list/show` 等）
- `utils/wiring/` 下的 wiring（“权威装配”）
- `plugins/base.py` 的插件契约（hook 名称与基本语义）
- `utils/context/context_schema.py` 的最小 context schema

### 1.2 Provisional（试用 / 可能变）

满足以下条件之一，视为 Provisional：
- 已经进入主仓库并在示例/文档中使用，但尚未形成稳定契约与测试覆盖
- 处在快速迭代期，参数名/输出结构可能调整

对 Provisional 的承诺：
- 尽量保持兼容
- 允许在 MINOR 版本中做“合理重构”，但仍建议先给出弃用提示

### 1.3 Experimental / Internal（实验 / 内部）

默认规则：
- 历史 `deprecated/legacy/`（已从仓库清理）：明确不承诺稳定
- 以 `_` 开头的符号：内部实现细节
- `core/solver.py` 内部字段/非公开方法：内部实现细节（除非明确列为 Stable）

对 Experimental / Internal：
- 可以随时更改/删除
- 仅用于探索或实现细节，不建议外部依赖

## 2. 对外 API 的设计原则

- Top-level namespace 保持小：`import nsgablack` 不应触发大量副作用
- 主路径以“装配层（wiring）+ 能力层（plugin）+ 策略层（adapter）”为中心，避免用户直接依赖 solver 内部细节
- 新能力优先以 Plugin/Wiring 形态落地；进入 Core 前必须具备：
  - 明确契约（输入/输出/错误模式）
  - 对应测试
  - catalog 条目（可发现性）

## 3. 弃用策略（Deprecation Policy）

### 3.1 最小弃用周期（推荐）

- 先弃用（Deprecate）：至少跨 1 个 MINOR 版本保留兼容
- 再移除（Remove）：进入下一个 MAJOR 或声明的 remove_in 版本

### 3.2 弃用实现规范

- 兼容层统一放在 `utils/compat/`
- 兼容 wrapper 必须发出 `DeprecationWarning`，并包含：
  - old 符号名
  - new 符号名/迁移路径
  - remove_in（计划移除版本号）

建议使用统一工具函数（见 `utils/compat/deprecation.py`）。

### 3.3 文档与测试要求

- 文档：Stable 文档只指向新路径；旧路径只保留“迁移提示”
- 测试：必须增加 smoke test 覆盖新路径，避免未来重构误伤

## 4. 破坏性变更（Breaking Changes）判定

以下任一情况视为 Breaking：
- 删除/重命名 Stable API（符号、参数、返回结构）
- 改变 Stable 输出文件的 schema（例如 benchmark summary 字段语义变化）
- 改变插件 hook 的名称或调用时机

若必须 Breaking：
- 提前在 CHANGELOG 中标注
- 提供迁移指南（最小替换方案）
- 在 MAJOR 版本发布时进行

