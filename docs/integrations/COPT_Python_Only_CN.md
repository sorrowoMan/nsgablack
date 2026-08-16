# COPT 用户手册（仅 Python 部分）整理稿

> 来源：`C:\Program Files\copt80\docs\copt-userguide_cn.pdf`  
> 版本：COPT 8.0.3（文档内标注）  
> 说明：本稿仅整理 Python 相关内容，不包含 C/C++/C#/Java/AMPL/Pyomo/PuLP/CVXPY 章节。

---

## 1. Python 章节范围（按目录页码）

- `7.5 Python接口`：约第 **114–121** 页
  - 安装说明（Windows/Linux/macOS）
  - 示例解析（`lp_ex1.py`）
  - 最佳实践（升级、镜像、多线程、字典顺序）
- `Python API参考手册`：从约第 **449** 页开始
  - `COPT` 常数类
  - 建模核心类（`Envr`、`Model`、`Var`、`Constraint`、`MVar`、`CallbackBase` 等）
  - 辅助函数与工具类（`quicksum`、`multidict`、`tupledict`、`tuplelist` 等）

---

## 2. 安装与环境（Python）

### 2.1 版本与平台要点

- 文档给出的 Python 支持区间：`3.7–3.13`。
- 文档建议优先用 `3.8–3.13`（矩阵建模能力最低要求 3.8）。
- Windows 下不建议使用 Microsoft Store 版 Python。

### 2.2 推荐安装方式（pip）

```bash
pip install coptpy
pip install --upgrade coptpy
```

### 2.3 离线安装方式（安装包目录）

- 进入 `copt80/lib/python` 目录后执行：

```bash
python setup.py install
```

### 2.4 验证安装

- 在 `copt80/examples/python` 目录运行示例 `lp_ex1.py`。
- 若模型可正常求解，则接口配置基本正确。

### 2.5 升级建议

- 文档建议：升级前先卸载旧版，再安装新版。
- 若历史使用 `setup.py install`，需手工清理 `site-packages` 下旧的 `coptpy` 与 `coptpy-*.egg-info`。

---

## 3. Python 建模求解主流程（最小闭环）

文档示例的标准流程如下：

1. 导入接口
2. 创建环境 `Envr`
3. 创建模型 `Model`
4. 添加变量 `addVar/addVars`
5. 添加约束 `addConstr/addConstrs`
6. 设置目标 `setObjective`
7. 设置参数 `setParam`
8. 调用求解 `solve`
9. 读取结果（状态、目标值、变量值、基状态）
10. 导出模型/解文件（`write`）

示例骨架（与文档风格一致）：

```python
import coptpy as cp
from coptpy import COPT

env = cp.Envr()
model = env.createModel("demo")

x = model.addVar(lb=0.0, ub=10.0, name="x")
y = model.addVar(lb=0.0, ub=10.0, name="y")

model.addConstr(x + y <= 8)
model.setObjective(2.0 * x + 3.0 * y, sense=COPT.MAXIMIZE)
model.setParam(COPT.Param.TimeLimit, 10.0)

model.solve()
if model.status == COPT.OPTIMAL:
    print("obj=", model.objval)
```

---

## 4. Python API 参考结构（实用视角）

以下是 Python API 参考手册中最常用的能力分组（按功能理解，不逐项抄录）：

### 4.1 环境与模型生命周期

- `Envr`：创建/关闭求解环境。
- `Model`：创建变量、约束、目标；设置参数；求解；读写模型与解文件。

### 4.2 变量与约束建模

- 变量：`addVar` / `addVars` / `addMVar`。
- 线性约束：`addConstr` / `addConstrs` / `addMConstr`。
- 二次/锥/指数锥/半定/非线性：对应 `addQConstr`、`addCone*`、`addExpCone*`、`addPsd*`、`addNlConstr*`。

### 4.3 求解与结果读取

- 求解：`solve` / `solveLP`。
- 读取：`objval`、`getValues`、`getSlacks`、`getDuals`、`getAttr/getInfo`。
- 可行性诊断：`computeIIS`、`feasRelax*`。

### 4.4 回调与高级控制

- `setCallback` + `CallbackBase`：支持用户割、懒约束、中断、读取中间信息等。

### 4.5 工具函数

- `quicksum`、`multidict`、`tupledict`、`tuplelist` 等用于高效建模表达。

---

## 5. 文档中的 Python 最佳实践要点

### 5.1 镜像安装

- 网络较慢时可使用镜像源安装 `coptpy`。

### 5.2 多线程

- 文档强调：建模 API 不保证可重入。
- 一般可共享 `Envr`，不建议多个线程并发共享同一个 `Model` 做建模/求解。
- 常见做法：一个线程求解，另一个线程监控并在必要时 `interrupt()`。

### 5.3 字典顺序

- Python 3.7+ 保持字典插入顺序，推荐在 3.7+ 环境使用以避免顺序不稳定对建模次序的影响。

---

## 6. 面向你当前框架（nsgablack）的接入建议

如果你在框架里只用 COPT 的“线性求解能力”，推荐采用：

- `L4`：`EvaluationModelProviderPlugin`
- `Backend`：`CoptBackend`
- `builder`：仅实现 `copt_linear_spec_builder(request) -> {c, A, rhs, sense, lb, ub, vtype}`

这样可以做到：

- 保持 L4 短路评估语义不变；
- 后端能力收敛在 `BackendSolveRequest -> Mapping` 标准契约；
- 后续想扩展到 QP/QCP/MIP callback 时，不影响外层调度结构。

---

## 7. 建议你下一步优先补的三件事（Python 侧）

1. **状态码映射表**：把 `model.status` 映射成框架统一状态（`ok/non_optimal/infeasible/...`）。
2. **结果字段统一**：标准化输出 `objective/objectives/violation/metrics/solution`。
3. **一份真实 LP 回归样例**：固定输入、固定参数，验证每次输出结构一致。

---

如果你需要，我可以在这份文档基础上再生成一版《COPT Python 接入 nsgablack 的落地清单（含代码模板）》。
