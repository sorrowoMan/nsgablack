# NSGABlack

为什么复杂优化实验会“悄悄退化”，以及我如何试图让它变得可见。

这是一个  **仍在快速演化中的实验性框架** 。

我分享它是为了讨论思想，而不是作为已完成的产品。

算法解构的优化生态框架：把“问题/表示/偏好/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。

如果你和我一样，做优化项目时最怕的是这些情况：

* 代码能跑，但每次结果都像“玄学”。
* 想加并行、日志、checkpoint，最后把算法主循环写乱。
* 改了很多东西，却说不清到底是哪一层带来了变化。

我做 NSGABlack 的目的很直接：

> 让优化项目从“脚本堆叠”变成“可分层、可治理、可复现”的工程系统。

---

## 核心结构（四层正交）

- **Solver**：控制平面与生命周期（调度、评估入口、状态管理）
- **Adapter**：算法策略平面（`propose/update`）
- **Representation**：表示平面（init/mutate/repair/encode/decode）
- **Plugin**：能力平面（日志、评估短路、checkpoint、审计）

---

## 关键能力

- 多目标优化与多策略编排（NSGA2/3、SPEA2、MOEA/D、VNS、SA、DE 等）
- L4 评估路径与代理评估接入（surrogate/approximate）
- Context/Snapshot 分层存储与可回放
- Catalog 可发现性索引与双口径统计（`default` / `framework-core`）
- 标准化脚手架与工程治理（Project Doctor / Run Inspector）

---

## 2 分钟起步

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

---

## 目录结构

- `core/`：求解器主干与运行语义
- `adapters/`：算法策略层
- `representation/`：表示与算子管线
- `plugins/`：工程能力层
- `bias/`：偏置系统（软引导）
- `catalog/`：组件索引与筛选规则
- `project/`：脚手架与工程治理
- `examples/`：案例与演示
- `tests/`：回归测试

---

## 文档入口

1. `START_HERE.md`
2. `QUICKSTART.md`
3. `WORKFLOW_END_TO_END.md`
4. `docs/architecture/README.md`
5. `docs/architecture/COPT_INTEGRATION.md`

---

## Catalog 口径提醒

- `default`：完整口径（含 example/doc）
- `framework-core`：主干口径（排除 example/doc）

架构审计与主干盘点请显式带 `--profile framework-core`。
