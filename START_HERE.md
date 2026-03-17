# START_HERE：先跑通，再变强

这份文档是给“现在就要把项目落地”的你准备的。
我不假设你已经熟悉框架内部，只给你最短、最稳、不绕路的路径。

---

## 你今天的目标（先别追最优）

我建议你今天只拿下这三件事：

1. 项目能稳定启动。
2. 闭环能完整跑完。
3. strict 审查能通过。

先做到这三件事，后面再谈性能和效果，节奏会快得多。

---

## 第 1 步：15 分钟最小启动路径

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

这一轮重点看：

- `build_solver.py` 是否只做装配。
- 是否有 import 阶段重计算。
- doctor 是否已清零 error。

---

## 第 2 步：按这个顺序组装（非常关键）

顺序不要乱，乱了就容易变量过多无法归因。

1. `Problem`：先让 `evaluate(x)` 稳定。
2. `Pipeline`：先保证可行解生成与修复。
3. `Adapter`：先单策略跑通闭环。
4. `Bias`：再加软偏好，保证可解释。
5. `Plugins`：最后加并行、checkpoint、trace、报告。

---

## 第 3 步：三条硬规则（请直接照做）

1. 状态写入统一走 `solver.*`。
2. 小字段走 `ContextStore`。
3. 大对象走 `SnapshotStore`。

统一读写接口：

- `solver.read_snapshot()`
- `Plugin.get_population_snapshot()`
- `Plugin.commit_population_snapshot()`

守住这三条，架构会非常稳。

---

## 第 4 步：按角色找入口

### 我先跑项目

- `README.md`
- `WORKFLOW_END_TO_END.md`

### 我开发 Adapter

- `adapters/`
- `docs/architecture/README.md`
- `tests/test_*adapter*.py`

### 我开发 Plugin

- `plugins/`
- `docs/user_guide/CONTEXT_CONTRACTS.md`
- `tests/test_*plugin*.py`

### 我做治理与平台

- `project/doctor.py`
- `catalog/*`
- `docs/project/CONTRIBUTING.md`

---

## 第 5 步：常见卡点与处理

### 卡点 A：能跑，但结果不稳定

优先查：

- seed 是否固定。
- `evaluate` 是否有副作用。
- 并行是否有共享状态污染。

### 卡点 B：Doctor 报违规写入

优先查：

- 是否直接写了 `solver.population/objectives/...`。
- 是否绕过了 `solver.*` 控制面。

### 卡点 C：改太多，不知道谁起作用

处理方式：

- 每轮只改一层。
- 每轮改完完整复跑。

---

## 第 6 步：固定你的日常命令

```powershell
python -m nsgablack project doctor --path . --strict
python -m pytest -q
```

把这两条当作“出门前检查”：
doctor 看结构，pytest 看行为。

---

## 如果你现在只看一份进阶文档

看 `WORKFLOW_END_TO_END.md`。
那份文档是“我在你旁边陪跑”的完整步骤版。

---

## Doctor IDE 自动诊断

为了做到“保存即爆红/爆黄”，建议按这个最小路径配置：

1. 第一次打开仓库先点 `Trust`（信任工作区）。
2. 安装 `.vscode/extensions.json` 推荐扩展：
   - `Gruntfuggly.triggertaskonsave`
   - `ms-python.python`
   - `ms-toolsai.jupyter`
3. 检查配置文件：
   - `.vscode/settings.json` 已启用 `triggerTaskOnSave.*`
   - `.vscode/tasks.json` 有 `doctor: strict (problem)`
4. 保存 `.py/.toml/.json/.yml/.yaml/.md` 后，Doctor 会把诊断推到 `Problems` 面板。

### 为什么 Notebook 里看不到爆红

`ipynb` 的 cell 输出是执行日志，不是 VSCode `Problems` 诊断源。
定位错误请始终看 `Problems`，它会给出文件、行号和规则码。

### 排查顺序

1. 用 `File > Open Folder` 打开仓库根目录（不要只开单文件）。
2. 确认扩展 `Trigger Task on Save` 已启用，且 `task.allowAutomaticTasks` 为 `on`。
3. 在 `Terminal > Run Task` 能手动运行 `doctor: strict (problem)`。
4. 仍无反应时执行 `Developer: Reload Window` 再试一次保存。
