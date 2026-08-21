# 文档权威与清理规则

本文定义三仓现行文档的维护边界。它是治理规则，不重复讲解框架 API。

## 权威顺序

发生冲突时按以下顺序判断：

1. 当前源码与通过的测试。
2. 仓库 `AGENTS.md` 和包版本/依赖声明。
3. 根 `README.md`、`docs/README.md` 与当前标准脚手架教程。
4. 专题架构、用户指南和示例 README。
5. research、whitepaper 草稿和 Git 历史。

后一级不能覆盖前一级。

## 单一入口

- 每个仓库：一个根 `README.md`。
- 每个 Project：一个 `README.md`。
- 每个 Case：一个 `README.md`。
- 每个 docs 一级目录：一个 `README.md` 负责导航。

不再创建：

- `START_HERE.md`
- `BUILD_SOLVER_REGISTRATION.md`
- `COMPONENT_REGISTRATION.md`
- 复制到每个 Case 的 `COMPONENT_CONTRACT_TEMPLATE.md`
- 只解释目录名的空壳 README
- 与当前 README 重复的实现总结、迁移清单和 AI 记忆文件

组件、资源、输入输出、运行命令和限制都写入所属 Project/Case 的 README。正式契约写入代码、类型和 Doctor 规则，不靠复制模板维持。

## 三仓内容边界

- `blackbase`：Project/Stage/Case/Scaffold、L0、Context/Snapshot/Artifact、公共调用与结果协议。
- `nsgablack`：Solver、CandidateBatch、Representation、Adapter、Bias、Plugin、目标/约束、Pareto。
- `mlblack`：DataView、Spec、Codec、Head、LearningProblem、Evaluation Provider、backend capability、模型 Artifact。

`mlblack` 文档可以使用“训练、epoch、optimizer”等 ML 词汇，但必须说明它们如何投影到统一 Solver，而不能写成独立控制平面。`nsgablack` 文档不得把 ML backend 或模型语义硬编码进 Adapter。

## 历史材料

错误或已过期的文档直接删除，历史由 Git 保存。不要在现行文档树维护 `archive/`，因为搜索、Catalog 和 AI 检索仍会把 archive 当成候选事实。

白皮书只保留当前 V6 草稿；旧版本不与当前指南并列。

## 变更检查

文档变更至少验证：

- Markdown 本地链接指向真实文件。
- Catalog 的 `example_entry` / doc pointer 指向真实入口。
- 示例 README 声明的组件与 `--check --build-check` 一致。
- 不出现已删除的导入路径或私有控制面。
- 教程与介绍类文档以中文为主；英文另建独立文件。
- Doctor 不再要求生成重复文档。

文档数量不是质量指标。规则只写一次，其他位置通过链接复用。
