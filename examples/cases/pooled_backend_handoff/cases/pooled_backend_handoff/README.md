# Pooled Backend Handoff（计算后端线程池手递手）

验证 L0 线程池 + L4 评估后端（CoptBackend）通过存储做状态交接，实现计算资源不锁死。

## 是否使用 mlblack / nsgablack

🟦 纯 nsgablack（外层编排 + L4 评估运行时 + CoptBackend）

## 这个 case 验证什么

NSGA2 外层搜索与 COPT 数值求解后端共享同一批线程。外层提出候选 → 写入 L0 store → 释放线程 → COPT 获取线程 → 读取候选 → 调用真实 LP 求解器 → 写回结果 → 释放线程 → 外层读取结果继续。

核心断言：**计算资源（线程）是池化的，不是租约锁定的**。outer 和 copt 轮流使用同一批线程，L0 存储（context/snapshot）做交接缓冲。不存在"outer 占 4 线程 + copt 占 4 线程 = 总共 8 线程"的浪费。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x0, x1, x2 | 连续决策变量 | [-5.0, 5.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i²，通过 COPT LP 求解 |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Solver | EvolutionSolver (NSGA2Adapter) | 框架 core/evolution_solver |
| Problem | PooledHandoffProblem | 自定义（演示线程手递手日志） |
| Representation | RepresentationPipeline (GaussianMutation) | 框架 representation/ |
| Adapter | NSGA2Adapter | 框架 adapters/nsga2 |
| L4 | CoptHandoffProvider (包装 CoptBackend) | 框架 plugins/solver_backends/copt_backend |
| L0 | local_cpu runtime profile + PoolScheduler | 框架 core/resources/pool |

## 效果对比

本 case 是架构演示（编排模式的验证），不是算法性能对比。关键指标：

| 指标 | 传统租约模型 | 池化手递手模型 |
|---|---|---|
| 线程占用 | outer 4 + copt 4 = 8 线程锁定 | 共享 4 线程交替使用 |
| 状态交接 | 内存变量（线程释放即丢失） | L0 store（持久，线程无关） |
| COPT 集成 | mock 模拟 | 真实 CoptBackend.solve() |

## 结构

| 路径 | 作用 |
|---|---|
| `solver/config.py` | 求解器核心配置（pop_size=4, max_generations=1） |
| `problem/example_problem.py` | PooledHandoffProblem：最小单目标评估 |
| `problem/config.py` | 问题注册表（pooled_handoff profile） |
| `evaluation/copt_provider.py` | L4 评估提供者，包装 CoptBackend + 线程手递手日志 |
| `evaluation/config.py` | L4 provider 注册（copt_handoff） |
| `runtime/config.py` | L0 运行时配置（local_cpu） |
| `build_solver.py` | 标准脚手架组装入口 |
| `run_solver.py` | CLI 入口 |

## 运行和验证

```powershell
# 先进入 nsgablack 仓库根目录

# COPT 未装时自动降级 mock
python examples\cases\pooled_backend_handoff\run_project.py --check

# Python 3.13 + COPT 8.0 真实求解
$env:PYTHONPATH = "."
$env:PATH = "C:\Program Files\copt80\bin;$env:PATH"
python -c "import os; os.add_dll_directory(r'C:\Program Files\copt80\bin')"  # 一次性设置
python examples\cases\pooled_backend_handoff\run_project.py

# 医生检查
python -m nsgablack project doctor --path examples\cases\pooled_backend_handoff --build --strict
```
