# Catalog / Suites（可发现性 + 权威装配）

当你在框架里遇到这类问题时：

- “VNS / MOEA-D / 多策略协同 到底在哪？是 Bias 还是 Adapter 还是 Plugin？”
- “有没有官方推荐的组合方式？我怕漏配，结果口径对不上。”
- “我不想翻源码，能不能直接搜索到‘推荐入口’？”

你应该先用 `catalog` 做“定位”，再用 `suite` 做“权威装配”。

## 1) Catalog 是什么

`nsgablack.catalog` 是一个轻量注册表，用来回答：`where is X?`

它只做三件事：

- 给每个现代组件一个稳定的 `key`（可搜索、可引用）
- 标注组件类型 `kind`（`problem/representation/bias/adapter/plugin/suite/tool/...`）
- 给出 `companions`（软链接：推荐搭配的组件）

它刻意保持“小而权威”：只收录当前框架认可的现代路径，不把历史/实验代码混进来。

## 2) 怎么用（Python）

```python
from nsgablack.catalog import get_catalog

catalog = get_catalog()

# 1) 搜索：where is X?
for e in catalog.search("vns"):
    print(e.key, e.kind, e.title)

# 2) 列表：某一类组件有哪些
for e in catalog.list(kind="suite"):
    print(e.key)

# 3) 跳转：加载符号（动态 import）
VNSAdapter = catalog.get("adapter.vns").load()
```

## 3) 怎么用（命令行）

建议在仓库上一级目录运行（或先 `pip install -e .`）：

```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog search suite
python -m nsgablack catalog list --kind adapter
 python -m nsgablack catalog show adapter.vns
 python -m nsgablack catalog show suite.multi_strategy
 ```

## 3.5) Run Inspector（Tk，运行前审查 wiring）

Run Inspector 会读取当前 solver wiring，并基于 Catalog 的 `companions` 提示缺失搭配。

```bash
python utils/viz/visualizer_tk.py --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

也可以用统一入口：

```bash
python -m nsgablack run_inspector --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

## 4) Suites 是什么（为什么“推荐用 suite 装配”）

框架里有些能力“必须成套才有意义”，比如：

- 统一实验口径：BenchmarkHarness + ModuleReport + Profiler
- 多策略协同：MultiStrategyController + ParetoArchive + 合理的 pipeline/bias
- 分布式/大规模评估：ParallelEvaluator(ray) + problem_factory + 合理的 chunk/容错策略

这类场景不推荐让用户“靠记忆手动拼装”；推荐提供一键装配入口（Suite）。

```python
from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report

solver = ...
attach_benchmark_harness(solver)
attach_module_report(solver)
```

Suite 也会被 Catalog 收录为 `kind="suite"`，并通过 `companions` 指向其推荐搭配组件。

## 5) 如何新增条目（不改 Python 源码）

仓库内推荐在 `catalog/entries.toml` 添加条目（再 `python -m nsgablack catalog reload`）。

示例：

```toml
[[entry]]
key = "adapter.my_algo"
title = "MyAlgoAdapter"
kind = "adapter"
import_path = "nsgablack.core.adapters.my_algo:MyAlgoAdapter"
tags = ["my_algo", "hybrid"]
summary = "自定义策略内核（adapter）。"
companions = ["plugin.pareto_archive", "suite.benchmark_harness"]
```

## 6) 设计边界（为什么不做成更重的 IoC 容器）

- Catalog 是“可发现性层”，不是依赖注入系统：它可以扩展，但不会变成强耦合的装配中心。
- 权威装配由 Suite 表达：Suite 是显式、可读、可测试的“事实标准”。
