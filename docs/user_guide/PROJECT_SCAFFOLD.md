# 创建项目骨架（Project Scaffold）

这份文档只回答一件事：如何用 NSGABlack 快速起一个**可直接开工**的新项目结构。

## 1) 一条命令创建

在框架仓库根目录执行：

```powershell
python -m nsgablack project init my_project
```

创建后进入项目目录：

```powershell
cd my_project
```

## 2) 会生成什么

`project init` 会生成如下结构：

```text
my_project/
  problem/
  pipeline/
  bias/
  adapter/
  plugins/
  data/
  assets/
  README.md
  START_HERE.md
  COMPONENT_REGISTRATION.md
  build_solver.py
  project_registry.py
```

各层职责：
- `problem/`：问题定义（目标、约束、维度、边界）
- `pipeline/`：表示与硬约束（初始化/变异/修复/编码）
- `bias/`：软偏好与搜索倾向
- `adapter/`：策略编排（需要时再加）
- `plugins/`：工程能力（并行、记录、回放、监控等）
- `data/`：输入数据
- `assets/`：输出产物（图、报表、导出）
- `COMPONENT_REGISTRATION.md`：组件注册说明（做什么、为什么、怎么做）

## 3) 创建后第一轮检查

先做结构与接线体检，再跑：

```powershell
python -m nsgablack project doctor --path . --build
python build_solver.py
```

`doctor --build` 会检查：
- 目录和关键入口是否齐全
- `build_solver()` 是否可实例化
- 组件契约是否清晰（如 `context_requires/provides/mutates`）
- 根目录是否有 `COMPONENT_REGISTRATION.md`（用于提醒注册规范）
- `project_registry.py` 的 usage 契约是否齐全（`use_when/minimal_wiring/required_companions/config_keys/example_entry`）

## 4) 本地 Catalog 怎么用

初始化后，本地组件可通过 project catalog 查找：

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search context_requires --field context --path .
```

需要同时搜索框架全局组件时加 `--global`：

```powershell
python -m nsgablack project catalog search vns --path . --global
```

## 5) 用 Run Inspector 看结构

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

常用查看点：
- `Catalog`：搜索组件与契约
- `Context`：看上下文字段
- `Contribution`：看组件贡献

## 6) 常见问题

- 目标目录非空时报错：换新目录，或显式 `--force` 覆盖模板文件。
- `project doctor` 不可用：先确认当前安装的是最新本地代码（建议在仓库根目录 `python -m pip install -e .`）。
- 导入失败：优先检查 `build_solver.py` 的导入路径和文件位置是否一致。
