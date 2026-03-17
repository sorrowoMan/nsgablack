# plugins/solver_backends

该目录现在只保留后端桥接与治理插件：
- `contract_bridge.py`
- `timeout_budget.py`
- `ngspice_backend.py`（后端实现）
- `copt_backend.py`（COPT 数值求解后端实现）

说明：
- 内层求解执行入口已从插件层移除。
- 统一改为 `problem.inner_runtime_evaluator`（见 `nsgablack.core.nested_solver`）。

## COPT backend 快速说明

`CoptBackend` 支持三种调用形态（优先级从高到低）：

1. `request.payload['copt_solve_fn'](request, coptpy)`：完全自定义求解逻辑。
2. `request.payload['copt_template'] + request.payload['copt_template_params']`：模板化求解（内置 `linear` 模板，可扩展）。
3. `request.payload['copt_linear_spec_builder'](request)`：返回线性模型规格（`c/A/rhs/sense/lb/ub/vtype`），由 backend 代建模并调用 COPT。
4. 无 builder 时可退化为 mock（`mock_when_unavailable=True`）。

模板化推荐约定：
- 由系统/策略层在 payload 显式指定 `copt_template`，避免自动猜测可建模性。
- 由 `copt_backend` 负责读参传参和模板求解执行。
- 求解输出统一走 backend 标准结果结构（`objective/objectives + violation + metrics`）。

模板实现组织：
- 建议每个模板一个文件，放在 `plugins/solver_backends/copt_templates/`。
- `copt_backend` 通过模板注册表加载默认模板，再允许构造参数 `template_solvers` 覆盖/扩展。

