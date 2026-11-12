# Catalog And Wiring Guide

当前架构的中文主说明见 [Catalog：从想法到可检查装配](../architecture/CATALOG_USAGE_CN.md)，包含 Pool／Unit、按用途搜索、可替换算法部件与本地网页。本页保留基础 CLI 和 Wiring 用法。

组件的输入、装配代码、依赖与预期输出见[逐组件使用示例说明](CATALOG_COMPONENT_EXAMPLES_CN.md)。目录中的“用法示例”和“已运行示例”分别表示源码绑定的使用说明、具有正式运行收据的示例；不要将导航链接或构造成功当成完整算法已经运行。

框架 AI 的认知资料、可追溯训练语料、独立评测与微调模型接入见[框架助手训练与验收](../development/FRAMEWORK_ASSISTANT_TRAINING_CN.md)。认知试验与完整在线装配任务分别验证。

Use Catalog when you need to answer:

- where is a component?
- what kind of component is it?
- which import path loads it?
- which companions are usually mounted with it?
- is this a framework-core entry or an example/doc entry?

## Profiles

`nsgablack` uses two catalog profiles:

| Profile | Meaning |
| --- | --- |
| `framework-core` | framework components only; use for architecture audits |
| `default` | full index including docs and examples |

Architecture conclusions must use `framework-core`:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

Use `default` when looking for tutorials or example entries:

```powershell
python -m nsgablack catalog list --profile default --kind example
```

## Python Usage

```python
from nsgablack.catalog import get_catalog

catalog = get_catalog(profile="framework-core")

for entry in catalog.search("vns"):
    print(entry.key, entry.kind, entry.title)

entry = catalog.get("adapter.vns")
adapter_cls = entry.load()
```

## Wiring

Wiring helpers are official assembly shortcuts for common capability bundles. They should still be called from standard Case assembly, usually `build_solver.py`.

Examples:

```python
from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report

attach_benchmark_harness(solver)
attach_module_report(solver)
```

Wiring helpers must not become private orchestration systems. Cross-Case order and resource allocation belong to Project / L0.

## Adding Entries

Add framework entries to the registry source, then verify both profiles:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog list --profile default --kind example
```

If an entry is a formal example, it should point to `examples/cases/<project>/run_project.py` or to a nested `cases/<case>/build_solver.py` import path inside that Project, not a compatibility wrapper.
