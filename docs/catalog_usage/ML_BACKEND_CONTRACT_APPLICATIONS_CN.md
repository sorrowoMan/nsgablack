# ML 后端契约参考：先查声明，再决定装配

本页只做了源码、Python 语法和来源绑定核对，未导入或构造后端、执行查询代码或模型计算。能力声明属于元数据；下面代码供使用者在本地配置诊断时调用，不是训练配方。

## mlblack.backend_capability.torch.tensor · 共享读取四后端的全部能力声明

**什么时候用：** 给已有模型选择后端前，想知道声明了哪些 tensor、模型 lowering、loss、autograd、optimizer 和 Artifact 接口，以及实际消费者要求的能力是否缺失。当前 Catalog 将四个后端的 22 个 capability 组件分别索引：NumPy 四个，Torch/JAX/TensorFlow 各六个。它们不是 22 个可独立训练的算法。本主例查询四个后端的所有 capability 声明，因此这些条目共用这一页完整用法。

**先准备什么：** 安装当前 blackbase、nsgablack、mlblack 及其基础依赖 NumPy。查询入口来自 `mlblack.backends`。先从实际 Problem/Representation 的 backend_requires 或 Provider 契约收集需求，不凭模型名称猜接口。本例读取 TinyCNNImageClassificationProblem 与 NeuralGraphRepresentation 的声明，再加真实的 `neural.lowering.cnn` 路由要求；这不是对任意 CNN 参数配置的全量验收。

注意查询的真实成本：`list_backends()` 首次会导入四个内置 backend 模块并登记工厂；`list_backend_capabilities/explain_backend_requirements` 会经过 get_backend，首次创建并缓存后端 facade 和它的能力组件。它不是零成本的静态 JSON 读取。当前 Tensor 能力中的 torch/JAX/TensorFlow 库调用使用延迟导入入口，但注册或包导入成功不能证明可选库安装完整；实际计算仍分别需要 torch、jax 或 tensorflow 等依赖与受支持版本。不要把这里的查询当成依赖自检或无依赖保证。

**放在哪：** 放在自己工程的配置检查模块或本地 Python 交互会话；调用者是准备装配模型的使用者，不挂到每次训练步、Case builder 的初始化采样或目录页面刷新中。本页不新建训练 Case/运行器，不创建 ResourceContext，也不申请设备。`read_backend_contracts` 返回纯字典/列表/元组，适合显示或保存诊断；不把后端对象写进共享 context、数据库说明或跨进程 payload。

**接入步骤：** 以下是完整主例，可在同一 Python 会话一次运行。它消费真实返回的声明和匹配结果，不调用张量、梯度、优化器或模型方法：

```python
import json
from mlblack.backends import (
    list_backends, list_backend_capabilities,
    explain_backend_requirements, resolve_backend,
)
from mlblack.problems.neural import TinyCNNImageClassificationProblem
from mlblack.representations.neural_graph import NeuralGraphRepresentation

def read_backend_contracts():
    requirements = tuple(dict.fromkeys((
        *NeuralGraphRepresentation.backend_requires,
        *TinyCNNImageClassificationProblem.backend_requires,
        "neural.lowering.cnn",
    )))
    registered = list_backends()
    rows = []
    for name in ("numpy", "torch", "jax", "tensorflow"):
        if name not in registered:
            raise ValueError(f"builtin backend was not registered: {name}")
        declarations = list_backend_capabilities(name)
        diagnosis = explain_backend_requirements(name, requirements)
        rows.append(dict(backend=name, capability_count=len(declarations),
            capabilities=declarations, requirement_check=diagnosis))
    selected_backend = resolve_backend(requirements, preferred="torch")
    return dict(requirements=requirements, registered=registered,
        backends=rows, selected_contract=selected_backend.contract().as_dict(),
        scope="declaration_match_only")

report = read_backend_contracts()
print(json.dumps(report, ensure_ascii=False, indent=2))
```

数据流是：读取消费者需求→列注册名→对每个名字取 capability 字典与缺失项→明确指定 preferred 做声明选择→只输出其 contract 字典。`resolve_backend` 返回缓存的后端 facade 实例；它不是 BackendSession、Provider、活模型或全局资源 grant。`selected_contract` 才是本例脱离出来的描述。

每条 capability 字典的 `provides` 是能力字符串，`methods` 是“能力/方法标识→接口说明”的映射；说明字符串不能当作 Python 方法直接执行。还可看 `requires/optional`、`tensor_kinds/model_kinds`、`routes/heads` 和支持标志。聚合 BackendContract.supports/missing 匹配 provides 或 methods 中的精确名称，不解析签名文本，不自动验证数据形状，也不递归安装 requires。`routes/heads` 和布尔标志仍要结合具体消费者读，不能用一个 supports_gpu=True 推断设备可用。

本例覆盖的实际组件包括：

- 四个后端都有 tensor、neural_lowering、losses、artifacts。
- Torch/JAX/TensorFlow 另有 autograd、optimizers；NumPy 没有这两个 capability 组件。
- JAX/TensorFlow 当前主要声明 functional MLP 梯度接口，不是 Torch 式 backward/module 模型的逐项替代；它们有 autograd 声明也不意味着满足本例 CNN 需求。

**怎样判断接对：** 在当前内置注册表下，四行 capability_count 应为 NumPy 4、其余各 6，总计 22；若部署加入了自定义后端，以 registered 和真实返回为准，不把旧计数当运行证据。每行 capabilities 应包含 backend/capability、真实 provides/methods 等字段，requirement_check 有 backend、ok、missing、requirements、provides。

本例的 Torch 声明包含 CNN lowering、分类 loss 和所需模式接口，preferred="torch" 的匹配返回 Torch contract；其他行按实际 missing 解释，不能因其 also 提供 neural.lowering 就断言 CNN 可用。`ok=True` **只表示这组名称匹配**，不表示依赖已安装、CUDA 存在、L0 已授权、模型/数据布局正确或训练已跑通。检查表不输出准确率、运行耗时或训练成功标记。

**运行入口：** 在准备好框架环境的本地 Python 交互会话中复制主例；终端可先进入 `python`。它只读取声明并打印 JSON，不需要 Project，也不执行 fit/run、下载权重或设备计算。查询本身仍可能因导入环境或注册错误抛异常；不要把这些异常改写成“模型缺能力”或静默选另一个后端。

将声明选择落实为训练配置时，仍须回到已有正式 Case 的工厂：完整图像接线见 `ML_STRUCTURED_INPUT_APPLICATIONS_CN.md`，由 `build_tiny_cnn_image_classification_trainer` 接收真实 data、`compute_backend="torch"` 和 Project 注入的 resource_context。不能把 selected_contract 当 resource_context，或把 facade 当模型传给 Problem。

### 变体一：明确 preferred 缺能力时拒绝，不悄悄回退

**目的：** 配置要求使用某个后端时，提前显示具体缺项；不能把“偏好 NumPy”解释为失败后自动切成 Torch。

**改在哪里：** 在同一配置诊断模块或主例之后追加以下完整函数和调用；report["requirements"] 来自主例的真实消费者声明：

```python
from mlblack.backends import explain_backend_requirements, resolve_backend

def inspect_preferred(preferred, requirements):
    requirements = tuple(requirements)
    diagnosis = explain_backend_requirements(preferred, requirements)
    try:
        selected = resolve_backend(requirements, preferred=preferred)
    except ValueError as exc:
        return dict(decision="rejected", diagnosis=diagnosis, reason=str(exc))
    return dict(decision="declaration_matched", diagnosis=diagnosis,
                selected_backend=selected.contract().name)

numpy_choice = inspect_preferred("numpy", report["requirements"])
print(json.dumps(numpy_choice, ensure_ascii=False, indent=2))
```

**行为变化：** 对当前声明，本例应进入 rejected：NumPy 缺少 CNN lowering、分类 loss 和有关模式接口。diagnosis.missing 给具体字符串，resolve_backend 的 ValueError 表示指定后端不满足这些要求，没有自动调用别的引擎。若换为满足要求的显式 preferred，返回的仍只是声明匹配结果。

**限制：** 此函数只把选择阶段的 ValueError 转成诊断，不吞掉导入错误；未知后端在 explain 阶段就可能抛错。若不提供 preferred，原 resolve_backend 按 list_backends 的名字排序选择首个匹配项，不做性能评估、依赖探测、设备申请或业务最优推荐；顺序会受注册表变化影响。准备训练时保持显式选择，并走原 Project/Case 的 Provider、BackendSession 与 L0 授权链。

源码依据：`mlblack/backends/registry.py`、`backends/contracts.py`、`backends/catalog.py`、四个 `backends/*_neural/backend.py::contract` 及各 `capabilities/` 的实际声明。这里只说明公开查询与名称匹配，没有执行后端计算。
