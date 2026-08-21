# nsgablack 文档入口

这组文档以当前统一框架栈为准：

> `nsgablack` 和 `mlblack` 共享统一的 Project / Case / Scaffold / L0 substrate。`nsgablack` 是优化搜索语义层，`mlblack` 是机器学习语义层。编排和资源授权属于 substrate，不属于任一语义层的私有能力。

## 推荐入口

| 文档 | 用途 |
| --- | --- |
| [standard_scaffold_tutorial/](standard_scaffold_tutorial/README.md) | 当前标准 Project / Case / Scaffold 教程，包括嵌套 Case 和 L0 资源 grant。 |
| [architecture/README.md](architecture/README.md) | Solver / Adapter / Representation / Plugin 边界，以及共享 substrate。 |
| [user_guide/README.md](user_guide/README.md) | 面向使用者的操作指南。 |
| [project/README.md](project/README.md) | 项目治理、发布流程、稳定性策略、ADR 与 run surface contract。 |
| [concepts/](concepts/README.md) | 功能总览、核心概念和框架哲学。 |
| [guides/](guides/README.md) | 组件边界、接入步骤和专题操作指南。 |
| [indexes/](indexes/README.md) | Catalog / API / 示例 / 工具索引。 |
| [integrations/](integrations/README.md) | 外部 solver、ML 工具、数据库等集成说明。 |
| [cases/](cases/README.md) | 案例说明与复现入口，正式可运行内容以 `examples/cases/<project>/run_project.py` 为准。 |
| [research/README.md](research/README.md) | 研究机制、系统叙事和 benchmark 解读，不作为架构权威。 |
| [project/DOCS_ARCHITECTURE_AUDIT.md](project/DOCS_ARCHITECTURE_AUDIT.md) | 文档清理规则和旧口径迁移基线。 |
| [project/AUTHORITATIVE_EXAMPLES.md](project/AUTHORITATIVE_EXAMPLES.md) | 什么样的示例才算正式示例。 |

## 当前有效规则

- 正式项目使用 `Project -> Case -> Standard Scaffold`。
- `run_project.py` 是 Project 正式入口。
- `project_config.py` 声明跨 Case 顺序和 Project L0 资源。
- `build_solver.py` 是 Case canonical assembly entry。
- `build_trainer.py` 如存在，只能作为 ML 命名习惯下的 alias。
- Case-level `runtime/` 只声明 requirement 和 audit，不拥有全局资源池。
- 大对象进入 Snapshot 或 Artifact，context 只放轻量字段和引用。
- 审计 framework-core 架构时使用 catalog `--profile framework-core`。

## 清理规则

仍然教学 legacy single-file demo、私有编排、Case-local 全局资源分配、`assembly/scaffold.json` 或 Case-level `capabilities/` 的文档，直接重写或删除。历史内容由 Git 保存，不再维护可被误认为现行说明的 archive 文档树。

仓库根目录只保留一个 README 导航入口。正文类文档放入对应的 docs 一级目录，避免根目录重新变成混合索引。
