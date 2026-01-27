# Catalog / Recipes (可发现性层)

当你在框架里遇到下面这种问题时：

- “TS/VNS/MOEA-D 这种东西到底在哪？是 Bias 还是 Adapter 还是 Plugin？”
- “某个组件有没有推荐配套（伙伴）？漏了会不会炸？”
- “有没有权威的一键装配入口，而不是靠记忆拼装？”

建议先用 `catalog` 做“定位”，再用 `suite` 做“权威组装”。

## 1. Catalog 是什么

`nsgablack.catalog` 是一个轻量注册表，用来回答“where is X?”，它不限制你怎么拆算法，只做三件事：

- 给每个现代组件一个 `key`（可搜索、可引用）
- 标注组件类型（Bias / Adapter / Plugin / Representation / Suite）
- 提供 `companions`（软链接：推荐配套组件）

它刻意保持“小而权威”：只收录当前框架认可的现代组件（不是历史大杂烩）。

## 2. 怎么用

```python
from nsgablack.catalog import get_catalog

catalog = get_catalog()

# 1) 搜索
for e in catalog.search("vns"):
    print(e.key, e.kind, e.title)

# 2) 列出某一类
for e in catalog.list(kind="plugin"):
    print(e.key)

# 3) 跳转到符号（动态 import）
vns_adapter_cls = catalog.get("adapter.vns").load()
```

## 2.1 命令行（更快的“它在哪”）

```bash
# 建议在项目上一级目录运行（或先 pip install -e .）
python -m nsgablack catalog search vns
python -m nsgablack catalog search vns --show-import
python -m nsgablack catalog list --kind adapter
python -m nsgablack catalog show adapter.vns
```

## 3. “Recipes” 在哪：Suite 就是权威 Recipe

框架里有一些能力“必须成套才有意义”，比如：

- “Monte Carlo 评估” + “鲁棒性信号驱动偏置”
- “MOEA/D adapter” + “Pareto archive 记录”

这种场景不推荐让用户手动记配件；推荐提供一键装配入口（Suite）。

你可以把 Suite 理解为“权威 recipe”（事实标准），用来避免漏配：

```python
from nsgablack.utils.suites import attach_monte_carlo_robustness

solver = ...
attach_monte_carlo_robustness(solver, mc_samples=16)
```

同时，Suite 也会被 catalog 收录为 `kind="suite"`，并通过 `companions` 指向其配套组件。

## 4. 设计约束（为什么不做成更重的系统）

- Catalog 是“可发现性层”，不是 IoC 容器：它可以扩展，但不会变成强依赖注入系统。
- Recipe 用 Suite 表达：Suite 是显式、可读、可测试的“权威拼装”，也符合“底座纯净”的理念。

## 5. 新拆一个算法，怎么让它可搜索（不改源码）

把条目写进 `catalog/entries.toml` 即可（repo 内扩展，最推荐）。例如：

```toml
[[entry]]
key = "adapter.my_algo"
title = "MyAlgoAdapter"
kind = "adapter"
import_path = "nsgablack.core.adapters.my_algo:MyAlgoAdapter"
tags = ["my_algo", "hybrid"]
summary = "我的新算法策略内核（adapter）。"
companions = ["plugin.pareto_archive", "bias.convergence"]
```

然后重新加载 catalog（可选；默认只在进程第一次 import 时加载）：

```python
from nsgablack import reload_catalog, search_catalog

reload_catalog()
print([e.key for e in search_catalog("my_algo")])
```

如果你希望“把条目放在别处”，可用环境变量：

- `NSGABLACK_CATALOG_PATH`：用 `;`（Windows）分隔多个 `.toml` 文件路径

## 5.1 可选：自动发现（不改 registry、不改集中列表）

如果你希望“新增一个模块后自动出现在 catalog”，可以在模块里放一个 `CATALOG_ENTRIES` 列表（Catalog 会自动扫描少量核心包：adapters/bias/representation/suites/plugins）：

```python
from nsgablack.catalog import CatalogEntry

CATALOG_ENTRIES = [
    CatalogEntry(
        key="adapter.my_algo",
        title="MyAlgoAdapter",
        kind="adapter",
        import_path="nsgablack.core.adapters.my_algo:MyAlgoAdapter",
        tags=("my_algo",),
        summary="我的新算法策略内核（adapter）。",
        companions=("suite.my_algo",),
    )
]
```

如需禁用自动发现（只用 TOML/环境变量），设置：`NSGABLACK_CATALOG_DISCOVERY=0`。
