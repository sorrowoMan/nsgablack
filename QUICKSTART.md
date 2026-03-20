# QUICKSTART

目标：5-10 分钟跑通一个最小闭环。

---

## 0) 环境

- Python 3.10+（推荐 3.11）
- 可选：Tk（Run Inspector 需要 GUI）

---

## 1) 安装

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
```

---

## 2) 创建脚手架

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

---

## 3) Catalog 搜索

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show adapter.multi_strategy
python -m nsgablack catalog search context_mutates --field context --kind plugin
```

---

## 4) 运行前审计（可选）

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

---

## 5) 核心质量门槛

```powershell
python -m nsgablack project doctor --path . --strict
python -m pytest -q
```

