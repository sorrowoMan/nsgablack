# DECOUPLING_CAPABILITIES: Plugin / Suite / Catalog 该负责什么

当你开始做真实问题，你会很快发现：你的麻烦往往不在“算法写不出来”，而在“工程能力不够稳定”。

这一页讲清楚三件事：
- Plugin：能力层（并行/记录/监控/短路评估）
- Suite：权威组合（把必配伙伴一次装好）
- Catalog：可发现性（你到底有哪些现成模块）

## Plugin：能力层（不污染底座）

适合做 Plugin 的事：
- 并行评估、缓存、批处理
- 统一实验口径输出（CSV/JSON）
- 监控/告警/统计信号（供 signal-driven bias 使用）
- 评估短路（例如 surrogate/缓存命中）

不适合做 Plugin 的事：
- 把策略过程写进来（那是 Adapter）
- 把硬约束修复写进来（优先在 RepresentationPipeline）

## Suite：权威组合（防漏配）

Suite 是“官方推荐装配方式”：把容易漏掉的伙伴组件（mutator/plugin/context keys）一次装齐。

当你遇到这些情况，优先用 Suite：
- 你第一次用某个策略/偏置系统
- 你怀疑自己漏接线（能跑但退化）
- 你要给别人一个“最少参数就能跑”的入口

## Catalog：可发现性（搜索/查看）

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.vns
```

如果你遇到报错：`No module named nsgablack`

解决方法（任选一种）：

1) 推荐：安装为可编辑包

```powershell
python -m pip install -e .
python -m nsgablack catalog search context
```

2) 快速试用：把父目录加到 `PYTHONPATH`

```powershell
$env:PYTHONPATH=".."
python -m nsgablack catalog search context
```

3) 在父目录运行

```powershell
cd ..
python -m nsgablack catalog search context
```

## 你应该看哪里

- Catalog 指南：`docs/user_guide/catalog.md`
- Plugins：`plugins/`
- Suites：`utils/suites/`

