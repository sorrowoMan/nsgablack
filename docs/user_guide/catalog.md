# Catalog 与 Suite 使用指南

当你不确定“组件在哪、该怎么装、是否漏配”时，先用 `Catalog` 定位，再用 `Suite` 装配。

## 1. Catalog 是什么
`nsgablack.catalog` 是轻量组件索引层，回答：`where is X?`

它主要提供：
- 稳定 `key`（可搜索、可引用）
- 组件类型 `kind`（problem/representation/bias/adapter/plugin/suite/tool/doc/example）
- 推荐搭配 `companions`

它不做依赖注入，只做可发现性。

## 2. Python 用法
```python
from nsgablack.catalog import get_catalog

catalog = get_catalog()

for e in catalog.search("vns"):
    print(e.key, e.kind, e.title)

for e in catalog.list(kind="suite"):
    print(e.key)

entry = catalog.get("adapter.vns")
adapter_cls = entry.load()
```

## 3. CLI 用法
```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog list --kind adapter
python -m nsgablack catalog show adapter.vns
python -m nsgablack catalog show suite.multi_strategy
```

## 4. Run Inspector 联动
Run Inspector 会基于 Catalog 的 `companions` 给出 wiring 提示。

```bash
python -m nsgablack run_inspector --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

## 5. Suite 是什么
`Suite` 是“权威装配入口”，适合成套能力：
- benchmark + report + profiler
- 多策略控制 + archive + 观测
- 并行评估 + 容错参数 + 工程护栏

示例：
```python
from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report

attach_benchmark_harness(solver)
attach_module_report(solver)
```

## 6. 如何新增 Catalog 条目
在 `catalog/entries.toml` 增加条目，再执行：

```bash
python -m nsgablack catalog reload
```

示例：
```toml
[[entry]]
key = "adapter.my_algo"
title = "MyAlgoAdapter"
kind = "adapter"
import_path = "nsgablack.core.adapters.my_algo:MyAlgoAdapter"
tags = ["my_algo", "hybrid"]
summary = "自定义策略内核。"
companions = ["plugin.pareto_archive", "suite.benchmark_harness"]
```

