# QUICKSTART（快速开始）

目标：**10 分钟跑通一个可复现实验**，并进入推荐工作流。

---

## 1) 安装（一次即可）

在 `nsgablack` 根目录：

```powershell
python -m pip install -e .
```

---

## 2) 推荐路径：创建新项目（不是直接改框架源码）

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build
python build_solver.py
```

这一步会得到：
- 标准目录结构（problem/pipeline/bias/adapter/plugins）
- 本地 `project_registry.py`
- 可运行的 `build_solver.py`

---

## 3) Catalog 基础用法（先学会找组件）

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack catalog search context_requires --field context --kind plugin
```

项目内搜索（本地 + 全局）：

```powershell
python -m nsgablack project catalog search context_mutates --field context --path . --global
```

---

## 4) Run Inspector（结构审计，不是画图工具）

在项目目录运行：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

你可以在 UI 里做：
- Catalog 搜索（`Match=context`）
- `context_requires` / `visualization prior` / `可视化先验` 关键词检索
- Context Tab 查看当前上下文字段

详见：`docs/user_guide/RUN_INSPECTOR.md`

---

## 5) 检查工具（建议加到日常）

```powershell
python tools/catalog_integrity_checker.py
python tools/catalog_integrity_checker.py --check-context
```

---

## 6) 下一步文档入口

- 推荐入口：`START_HERE.md`
- 端到端流程：`WORKFLOW_END_TO_END.md`
- 总手册：`docs/INDEX_MANUAL.md`
- context 契约：`docs/user_guide/CONTEXT_CONTRACTS.md`

---

## 7) 常见问题

### Q1：`No module named nsgablack`

重新执行：

```powershell
python -m pip install -e .
```

### Q2：`project doctor` 报 `contracts-not-explicit`

表示组件缺少 `context_*` 声明。  
先补 `context_requires / provides / mutates / cache / notes`，再运行 doctor。
