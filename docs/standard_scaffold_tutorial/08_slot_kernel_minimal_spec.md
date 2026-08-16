# 08. Slot Kernel 最小规范（nsgablack 版）

本章是可直接照抄的“从空 Case 到可运行”手册，目标是把 `pipeline/main.py` 变成真正可运行的统一编排入口。

## 0. 先讲清语义边界

`nsgablack` 与 `mlblack` 在 pipeline 语义上**不一样**，但共享同一个 slot kernel 编排契约。

- `nsgablack` pipeline 语义：搜索表示流（`init/mutate/repair/encode/decode`）
- `mlblack` pipeline 语义：训练数据/模型语义流（`transform/codec/head`）
- 共享点：都用一个 `pipeline/main.py` 主入口 + slot spec + operator registry

所以“统一”的是编排内核，不是把两个框架的语义混成一套。

---

## 1. 从空项目开始

在项目根目录执行：

```powershell
python -m nsgablack project new demo_slot_kernel_nsga
cd demo_slot_kernel_nsga
python -m nsgablack project add-case search_case --type solver --framework nsgablack
```

此时目录里会有：

```text
demo_slot_kernel_nsga/
  project_config.py
  run_project.py
  cases/
    search_case/
      build_solver.py
      pipeline/
        main.py
```

---

## 2. 用 CLI 生成 pipeline 内部算子

### 2.1 生成主入口（如果还没生成）

```powershell
python -m nsgablack project add-component --case search_case --kind pipeline --slot main --name main
```

### 2.2 生成 mutate / repair 算子

```powershell
python -m nsgablack project add-component --case search_case --kind pipeline --slot mutate --name gaussian_mutate
python -m nsgablack project add-component --case search_case --kind pipeline --slot repair --name clip_repair
```

会自动落到：

```text
cases/search_case/pipeline/operators/mutate/gaussian_mutate.py
cases/search_case/pipeline/operators/repair/clip_repair.py
```

---

## 3. `pipeline/main.py` 最小可运行装配

把 `cases/search_case/pipeline/main.py` 调整为如下结构（核心是两个输入：`pipeline_spec` + `pipeline_operators`）：

```python
from typing import Any, Mapping
from nsgablack.representation import PipelineSpec, build_pipeline_kernel


def build_pipeline(*, resource_context: Mapping[str, Any] | None = None, component_overrides: Mapping[str, Any] | None = None):
    del resource_context
    overrides = dict(component_overrides or {})
    registry = dict(overrides.get("pipeline_operators", {}) or {})
    spec = PipelineSpec.from_value(
        overrides.get("pipeline_spec", {"key": "default", "slots": ()})
    )
    kernel = build_pipeline_kernel(spec, operator_registry=registry)
    return kernel.representation_pipeline
```

---

## 4. 三种模式的完整 spec 示例

下面三组 spec 可以直接塞进 `component_overrides["pipeline_spec"]` 使用。

### 4.1 serial（串行）

```python
pipeline_spec = {
    "key": "serial_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "serial",
            "operators": ("gaussian_mutate", "clip_repair"),
        },
    ),
}
```

语义：先 `gaussian_mutate`，再 `clip_repair`。

### 4.2 parallel（并行分支 + merge）

```python
pipeline_spec = {
    "key": "parallel_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "parallel",
            "operators": ("wide_mutate", "local_mutate"),
            "merge": "mean",  # last/first/list/sum/mean/concat
        },
    ),
}
```

语义：两个分支都基于同一个输入跑，然后按 `merge` 合并。

### 4.3 router（按 context 路由）

```python
pipeline_spec = {
    "key": "router_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "router",
            "selector_key": "phase",
            "routes": {
                "explore": "wide_mutate",
                "exploit": "local_mutate",
            },
            "default_operator": "local_mutate",
            "strict": True,
        },
    ),
}
```

语义：`context["phase"]` 决定走哪个算子。

---

## 5. method 覆写（高级但很实用）

默认 slot 会映射到默认方法名（如 `mutate` slot 调 `mutate()`）。  
如果你要调用自定义方法，可在 slot 里加 `method`：

```python
{
  "slot": "head",
  "method": "predict",
  "operators": ("head_main",),
}
```

这在跨框架时尤其重要（例如 ml 侧 head 经常是 `predict/forward`）。

---

## 6. 运行时如何注入 spec 与 registry

在 `build_solver(...)` 里，把 `component_overrides` 透传给 `build_pipeline(...)`。

示意：

```python
pipeline_overrides = {
    "pipeline_spec": pipeline_spec,
    "pipeline_operators": {
        "gaussian_mutate": GaussianMutate(),
        "clip_repair": ClipRepair(),
        "wide_mutate": WideMutate(),
        "local_mutate": LocalMutate(),
    },
}
pipeline = build_pipeline(component_overrides=pipeline_overrides)
```

---

## 7. 可复制的验证步骤

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

建议至少验证：

1. serial 路径输出 shape 稳定
2. parallel merge 输出 shape 稳定
3. router 在不同 context 下路由正确

---

## 8. 常见错误与修复

### 错误 1：`pipeline operator not found`

原因：`pipeline_spec` 里写了名字，但 `pipeline_operators` 没注册。  
修复：统一命名，确保 spec/registry 一致。

### 错误 2：parallel merge 报错

原因：分支输出 shape 不兼容，或 merge 策略不匹配。  
修复：先用 `list` 收集，再检查每个分支输出；确认后再改 `mean/sum/concat`。

### 错误 3：router strict 模式 KeyError

原因：`selector_key` 在 context 中缺失或 route 未配置。  
修复：补 `default_operator`，或改 `strict=False`，或保证 context 注入。

---

## 9. 你可以直接复用的“起步组合”

### 组合 A：稳妥基线

- `mutate`: serial
- `repair`: serial
- 优先可复现

### 组合 B：探索/开发双模

- `mutate`: router(`phase=explore/exploit`)
- `repair`: serial
- 便于阶段策略切换

### 组合 C：多分支变异

- `mutate`: parallel + `merge=mean`
- `repair`: serial
- 适合多策略融合

---

## 10. 本章结论

`nsgablack` pipeline 的正确姿势是：

- Case 级只有一个 `pipeline/main.py`
- pipeline 内部用 slot kernel 组合算子
- 编排逻辑显式、可审计、可替换

这就是“统一 substrate + 搜索语义层”的可运行落地方式。
