# 2026-11-12 开发快照验证说明

本次 GitHub 提交用于保存和展示 nsgablack 的开发源码，不作为已完成全量验收的发行版。
blackbase 和 mlblack 是独立仓库，不包含在本次源码提交中。

## 已执行

- 对本次提交涉及的 1,036 个 Python 文件执行语法编译检查：未发现语法错误。
- 核心 Solver、SnapshotStore、接纳、父代槽位交接、Router 共同档案和算法修改任务：53 项测试通过。
- 暂存内容的 `git diff --cached --check` 通过；官方参考集保留原始 CRLF 字节，并声明对应空白检查属性。
- 检查本次源码及尚未推送的已有提交历史，未发现实际密钥；测试中的脱敏样例未作为真实凭据处理。
- 整体介绍中的本地文档链接存在。

本轮测试命令：

```powershell
python -m pytest tests/test_solver.py tests/test_snapshot_store.py tests/test_evaluation_acceptance.py tests/test_parent_member_handoff.py tests/test_composite_pool_maintenance.py tests/test_modification_tasks.py -q
```

测试环境为 Python 3.13.2，相关算法比较使用 pymoo 0.6.2，并依赖本机 blackbase 开发源码。
未执行全仓测试，也未完成干净机器的整套安装验证。

## Doctor 的真实结果

仓库工作区严格 Doctor 为 **29 errors、11 warnings、241 infos**。
其中 12 个 broad-except-swallow 来自 results 中保存的旧运行源码副本；这些运行产物没有进入本次提交。

将实际暂存的完整源码导出到新目录后，再执行同一条静态检查：

```powershell
python -m nsgablack project doctor --path <exported-source> --strict --catalog-audit --profile framework-core --format json
```

结果为 **17 errors、11 warnings、241 infos**，严格模式返回非零。
17 个错误集中在 runtime_cost_probe 的两个薄代理 Case：

- cases/production_inner：缺少两个 Trainer 薄别名入口及部分标准职责目录。
- cases/supply_adjustment_nested：缺少两个 Trainer 薄别名入口及部分标准职责目录。

这两个 Case 目前委托原 Case 的正式工厂进行性能诊断，与现行“每个 Case 都拥有完整脚手架”的检查存在不一致。
需要统一代理 Case 的表示方式或补齐有实际职责的脚手架，不能将检查结果写成通过。
11 条 warning 为部分 Case 缺少建议的 Pipeline 入口声明。

本次根目录 Doctor 没有使用 --build，不代表所有 Case 均已执行装配检查。
近期实际修改的 pool_workflow_pilot Project 已单独通过严格 Doctor/build，记录为
0 errors、0 warnings、28 infos；其 parallel_archive 分组已通过正式装配检查并真实运行。
这些局部结果不能替代全仓检查。

## 发布内容与复现边界

提交包括框架源码、测试、标准案例、公开文档、参考集及可移植部署脚本。
测试临时目录、运行数据库、checkpoint、实验输出、本机部署记录和密钥不上传。
运行产物仍保留在本地，未为提交删除。

已有文档中的 results 路径有些指向本地产物，应按相应 Project 命令重新生成。
首次阅读可从 [框架整体介绍](FRAMEWORK_OVERVIEW_CN.md) 和
[Pool Project](../../examples/cases/pool_workflow_pilot/README.md) 开始。
