# ML组件应用：每个目录页都能独立接线

本文是源码核对后的装配说明和可操作改造方案，未执行其中训练、测试或模型服务。每个公开键章节都独立写明正式宿主、完整builder、需要的新文件与实际消费者；不要求用户先阅读本书的其它组件章节。

路径相对mlblack仓库；公开键采用联邦Catalog前缀mlblack.。所有例子复用已存在的examples/cases/catalog_codec_demo Project及其linear_point Case。基础数据是公开合成数据，不读取业务文件；资源继续由正式Project的L0授权。

## mlblack.integration.learning_solver · 把数据、模型与搜索接成可运行Case

**什么时候用：** 要在正式Case中搜索模型参数，并取得最佳模型、原始反馈和ML报告。这里先用24条合成数据拟合一个两特征线性模型。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂也保留宿主现有24行2列的连续回归数据。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前两个代码块依次对应build_solver.py、pipeline/model.py；其它现有工厂按前提保留。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

**保留的实际数据工厂：** Case现有 `pipeline/main.py::build_pipeline(seed=17,n_samples=24)` 生成X为(24,2)、y为(24,)的连续回归数据，公式为 `1 + 2*x0 - 0.5*x1`。它已经返回NumericDataView，不需要为了阅读本组件重写一份数据层。

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 点输出、3个参数；数据不在Adapter中，梯度来自回归Problem。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：更换更新方法

目的：保留数据、模型和目标，只改变参数更新规则。

改在哪里：在原 `adapter/__init__.py` 中把 `gradient.sgd` 换成 `gradient.adam`，模型布局、DataView和Problem可保留：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    return build_optimization_adapter(
        "gradient.adam",
        learning_rate=float(learning_rate),
    )
```

行为变化：Adapter按Adam更新同一套参数，仍消费同一个Problem返回的梯度。

限制：学习率和总步数仍需按任务调整，不能因换成Adam就宣称效果更好。

### 变体二：模型没有梯度时继续使用同一装配

目的：改用不要求梯度的参数搜索，后续区间与分类例子复用这个入口。

改在哪里：将 `adapter/__init__.py` 换成下方高斯搜索工厂。保留 `learning_rate` 形参是为了匹配前面原有Case装配；此方法不消费学习率，实际变化尺度是 `mutation_scale`。

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

行为变化：每轮提出一批参数候选，评估后按可行性和所选目标聚合保留当前最佳，再围绕它生成后继。

限制：此处明确只用第一目标比较；若问题有多个目标，这不是Pareto搜索。想直接做Pareto选择可在同一个工厂返回nsgablack公开的多目标Adapter，需同时核对其初值、变化和模型语义候选支持。不能只把“方法名相似”当作可替换证明。

## mlblack.trainer.learning_solver · 同一个LearningSolver的Trainer目录入口

**什么时候用：** 从Trainer视角找到ML运行门面，同时保持唯一规范builder；这个键与integration.learning_solver指向同一个类，不应装配第二套训练循环。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂也保留宿主现有24行2列的连续回归数据。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前两个代码块依次对应build_solver.py、pipeline/model.py；其它现有工厂按前提保留。 第三个块是保持build_trainer.py为薄别名。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

**保留的实际数据工厂：** Case现有 `pipeline/main.py::build_pipeline(seed=17,n_samples=24)` 生成X为(24,2)、y为(24,)的连续回归数据，公式为 `1 + 2*x0 - 0.5*x1`。它已经返回NumericDataView，不需要为了阅读本组件重写一份数据层。

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

该Case的 `build_trainer.py` 继续保持唯一规范builder的薄别名：

```python
from .build_solver import build_solver as build_trainer
```

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** build_trainer只是build_solver的薄别名，仍运行同一套组件。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：复用同一实现的扩展点

目的：从目录的Trainer视角使用同一模型Case，改方法时不分叉第二套入口。

改在哪里：例如在该Case的 `adapter/__init__.py` 使用下方替换，规范builder和build_trainer薄别名保持一致：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    return build_optimization_adapter(
        "gradient.adam", learning_rate=float(learning_rate),
    )
```

行为变化：`build_solver`与`build_trainer`得到的是相同新方法装配，TrainerResult的读取方式不变。

限制：想把该训练作为优化问题的内层任务时，复用正式Case surface和Artifact/结果引用，资源继续由外层Project发放；alias本身不实现嵌套求解或资源申请。

## mlblack.data_view.numeric · 数值数据、标签与训练验证区域

**什么时候用：** 把二维特征和逐行标签交给学习Problem；本例先用24行两特征回归，再在本章变体中演示验证集与顺序切分。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂的完整替换代码在本章给出。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前三个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py；Problem与Adapter保持前提说明的宿主实现。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="output",
    )
```

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** DataView描述数据，Problem读取数据；24行数据不是24个模型参数。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：把验证误差作为模型选择依据

目的：让参数在训练集上更新，按未参与该更新的验证数据误差挑选模型。

改在哪里：在该 `pipeline/main.py` 使用公开的随机切分函数：

```python
import numpy as np
from mlblack.pipeline.data_views import train_valid_split


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return train_valid_split(
        X, y, valid_ratio=0.25, seed=int(seed),
        feature_names=("x0", "x1"), target_name="output",
    )
```

随后把 `problem/__init__.py` 改成以下工厂。只切出验证数据、仍保留原来的 `use_valid_objective=False`，不会自动改成验证集选择：

```python
from mlblack.problems import SupervisedRegressionProblem


def build_problem(data):
    return SupervisedRegressionProblem(data, use_valid_objective=True)
```

行为变化：反馈同时保留训练与验证指标，第一目标来自验证MSE；参数梯度仍由训练集计算。这表达“在训练集做更新、按验证集挑模型”。

限制：它不是在验证集上训练。检查 `best_feedback.signals["primary_objective"]` 和 `metrics["valid.mse"]`，不要只看到存在验证集就假定选择规则已改变；最终性能还需另留测试数据检验。

### 变体二：时间顺序不能打乱时，手工给出两段

目的：避免把时间靠后的行随机分配回训练区间。

改在哪里：以下替换同一数据工厂，默认24行时前18行训练、后6行验证；不用随机切分函数：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    del seed
    time = np.arange(int(n_samples), dtype=float)
    X = np.column_stack([time, np.sin(time / 3.0)])
    y = 1.0 + 0.2 * X[:, 0] - 0.5 * X[:, 1]
    cutoff = int(n_samples) - 6
    if cutoff <= 0:
        raise ValueError("该示例至少需要7行，且最后6行留作验证")
    return NumericDataView(
        X_train=X[:cutoff], y_train=y[:cutoff],
        X_valid=X[cutoff:], y_valid=y[cutoff:],
        feature_names=("time", "seasonal_feature"),
        target_name="future_output",
    )
```

同时替换本章 `problem/__init__.py`，明确让实际消费者使用验证目标：

```python
from mlblack.problems import SupervisedRegressionProblem


def build_problem(data):
    return SupervisedRegressionProblem(data, use_valid_objective=True)
```

行为变化：DataView按先后顺序持有两个区域，Problem按valid.mse选择候选；builder、PointHead和SGD保持本章基础接线。

限制：这只是手工按行分割的数值回归例子，不会自动创建滚动预测、窗口或防泄漏规则。真实时序任务还要核对特征生成时点；不能拿未来标签或未来统计量生成过去行。

## mlblack.codec.linear_point · 线性参数布局与模型往返

**什么时候用：** 确认参数数组每个坐标的含义，或从已有线性参数建立候选。正式运行中由LinearPointRepresentation内部调用LinearPointCodec，不额外挂第二份Codec。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂也保留宿主现有24行2列的连续回归数据。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前两个代码块依次对应build_solver.py、pipeline/model.py；其它现有工厂按前提保留。 第三个块是可选追加到pipeline/model.py的只读检查函数，不是另一个训练入口。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

**保留的实际数据工厂：** Case现有 `pipeline/main.py::build_pipeline(seed=17,n_samples=24)` 生成X为(24,2)、y为(24,)的连续回归数据，公式为 `1 + 2*x0 - 0.5*x1`。它已经返回NumericDataView，不需要为了阅读本组件重写一份数据层。

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 2个特征对应[intercept,w0,w1]三个参数，Codec不拥有搜索循环或种群关系。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

可选只读检查：在同Case的 `pipeline/model.py` 保留build_representation，再追加这个独立函数；它不会自动训练或入池。

```python
import numpy as np
from mlblack.models import LinearPointModel
from mlblack.representations.codecs import LinearCodecConfig, LinearPointCodec


def inspect_known_linear_model():
    codec = LinearPointCodec(LinearCodecConfig(
        n_features=2, feature_names=("x0", "x1"),
    ))
    known = LinearPointModel(
        intercept=1.0,
        weights=np.array([2.0, -0.5]),
        feature_names=("x0", "x1"),
    )
    values = codec.encode(known)
    restored = codec.decode(values)
    X = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    return values, restored.predict(X), codec.parameter_layout()
```

按固定参数代数，该函数应返回values=[1,2,-0.5]、预测[1,3,0]及截距/权重布局；这是计算预期，不是本次执行结果。

### 变体一：从已有模型参数开始运行

目的：让正式初始化使用业务已有的线性参数，编码后仍经过Solver的身份绑定、修复和求值。

改在哪里：替换本章已接入builder的 `pipeline/model.py`。builder无需再改，因为它已经实际调用build_representation：

```python
import numpy as np
from mlblack.models import LinearPointModel
from mlblack.representations import LinearPointConfig, LinearPointRepresentation


class KnownSeedRepresentation(LinearPointRepresentation):
    def init(self, context):
        del context
        model = LinearPointModel(
            intercept=0.5,
            weights=np.array([0.1, -0.1]),
            feature_names=("x0", "x1"),
        )
        return self.encode(model)


def build_representation(data, *, seed):
    if data.n_features != 2:
        raise ValueError("本例已有参数只对应两个特征")
    return KnownSeedRepresentation(LinearPointConfig(
        n_features=2,
        feature_names=data.effective_feature_names,
        random_seed=int(seed),
    ))
```

行为变化：运行时的初始化经Representation.encode调用实际Codec，产生[0.5,0.1,-0.1]的语义候选；之后仍由同一回归Problem评估，SGD消费其梯度。

限制：这不是checkpoint恢复，也不是把一个未求值数组直接插入已有Unit。模型结构、特征列顺序与这个已知参数必须匹配。

### 变体二：增添一个业务特征

目的：为模型增加第三列真实特征，同时让线性参数布局自动扩成四维。

改在哪里：只替换本章Case的 `pipeline/main.py`；保留本章基础模型工厂，因为它已经从data.n_features/effective_feature_names构造表示：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 3))
    y = 1.0 + 2.0*X[:, 0] - 0.5*X[:, 1] + 0.3*X[:, 2]
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1", "x2"), target_name="output",
    )
```

行为变化：builder取得3列DataView，模型表示内部Codec据此分配一个截距和三个权重；参数数变成4。仍使用同一回归Problem和SGD，不需要额外挂第二份Codec。

限制：旧3维候选、反馈或checkpoint不能直接解释成新4维模型。新建一次运行并核对模型dimension与权重长度，不能默默补零伪装原布局。

## mlblack.representation.linear_point · 模型候选的初始化、修复与解释

**什么时候用：** 让算法搜索线性模型的UnknownState，明确初始化、参数布局、输出Head和Problem如何连接；本章也给出业务已知初值和概率输出两个改法。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂也保留宿主现有24行2列的连续回归数据。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前两个代码块依次对应build_solver.py、pipeline/model.py；其它现有工厂按前提保留。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

**保留的实际数据工厂：** Case现有 `pipeline/main.py::build_pipeline(seed=17,n_samples=24)` 生成X为(24,2)、y为(24,)的连续回归数据，公式为 `1 + 2*x0 - 0.5*x1`。它已经返回NumericDataView，不需要为了阅读本组件重写一份数据层。

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 模型Codec维护参数布局，算法Unit维护搜索结构，二者不共享可写优化器状态。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：从业务已知参数开始

目的：让首个模型候选使用业务已知参数，而不改变Solver的候选初始化时点。

改在哪里：替换 `pipeline/model.py` 为下方工厂。仍由框架在运行初始化时调用 `init`；装配时不提前造候选、不创建另一个池。

```python
import numpy as np
from mlblack.core.types import UnknownState
from mlblack.representations import LinearPointConfig, LinearPointRepresentation


class WarmStartLinearRepresentation(LinearPointRepresentation):
    def init(self, context):
        del context
        return UnknownState(
            values=np.array([0.5, 0.1, -0.1], dtype=float),
            metadata={"source": "business_linear_seed"},
        )


def build_representation(data, *, seed):
    if data.n_features != 2:
        raise ValueError("这个已知初值只对应2个特征")
    return WarmStartLinearRepresentation(LinearPointConfig(
        n_features=2,
        feature_names=data.effective_feature_names,
        random_seed=int(seed),
    ))
```

行为变化：初始化产生 `[0.5, 0.1, -0.1]` 对应的模型候选，之后继续由原Problem求值、原Adapter更新。

限制：该变体保持默认PointHead，所以数组确实表示一个截距和两个权重。它不是恢复checkpoint；继续已有运行应走正式恢复入口，而不是重放这个init。

### 变体二：换输出而保留线性基础

目的：把当前点回归Case改为二元概率任务；保留本章完整builder，明确替换它实际消费的四个工厂。

改在哪里：以下四个文件都位于本章的catalog_codec_demo/cases/linear_point内，必须一起替换。仅新增Head而保留回归Problem或SGD，不能完成这个分类任务。

替换 `pipeline/main.py`，把连续标签改为0/1：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = (X[:, 0] - 0.5*X[:, 1] > 0.0).astype(int)
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="above_boundary",
    )
```

替换 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import BinaryLogisticHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=BinaryLogisticHead(classes=(0, 1)),
    )
```

替换 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=False,
        objective_metrics=("log_loss", "error_rate"),
    )
```

替换 `adapter/__init__.py`：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

行为变化：同一3维基础参数成为logit模型，输出两列概率；分类Problem产生log_loss/error_rate反馈，高斯搜索按第一目标log_loss比较。builder已经导入四个工厂，不需要另写控制循环。

限制：分类Problem不提供梯度。需要在运行后的result.best_model上读predict_proba，并从result.best_feedback.metrics读train.log_loss/train.error_rate；Head能够decode不等于对应Problem自动提供梯度。非PointHead的encode(model)当前未实现，不能用旧点回归结果反向编码来假装这个分类模型。

## mlblack.head.point · 单值输出、回归指标与梯度

**什么时候用：** 每行预测一个连续数值，例如产量或金额。PointHead使用一个基础线性块，配回归Problem后才具有本例的解析梯度。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 本节保留宿主已有problem/__init__.py的回归Problem工厂（use_valid_objective=False）与adapter/__init__.py的gradient.sgd工厂；它们是实际存在、被下面builder调用的消费者。 数据工厂也保留宿主现有24行2列的连续回归数据。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前两个代码块依次对应build_solver.py、pipeline/model.py；其它现有工厂按前提保留。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import PointHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=PointHead(),
    )
```

**保留的实际数据工厂：** Case现有 `pipeline/main.py::build_pipeline(seed=17,n_samples=24)` 生成X为(24,2)、y为(24,)的连续回归数据，公式为 `1 + 2*x0 - 0.5*x1`。它已经返回NumericDataView，不需要为了阅读本组件重写一份数据层。

**保留的实际Problem与Adapter：** Case已有 `problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem(data,use_valid_objective=False)`，已有 `adapter/__init__.py::build_adapter(learning_rate=...)` 返回 `build_optimization_adapter("gradient.sgd",learning_rate=...)`。上方builder确实调用这两个工厂；不需要新增同名未被引用的函数，也不要把MLTrainer放进Adapter。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 本例表示的dimension应为3，坐标为[intercept,w0,w1]；模型predict(X)返回(n_samples,)单值数组。回归Problem的原始objectives为[MSE,0]（复杂度权重默认0），梯度来自训练集；metrics有train.mse/train.rmse/train.mae/train.r2。读取loss正则项与原始目标时不要混为一个数。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。未显式配置scalarizer时默认sum，本例为MSE+0。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** Head负责输出形式，回归Problem负责MSE、指标和梯度；PointHead本身不是损失函数。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：加入L2更新偏好

目的：在参数更新时抑制权重过大，同时保留原始误差指标。

改在哪里：将 `problem/__init__.py` 改成以下工厂：

```python
from mlblack.problems import SupervisedRegressionProblem


def build_problem(data):
    return SupervisedRegressionProblem(
        data,
        l2=0.01,
        use_valid_objective=False,
    )
```

行为变化：这个实现的L2进入训练loss和解析梯度，`metrics["loss.regularized_train"]` 可读到它。

限制：第一原始目标仍是MSE。不能把它介绍成“原始MSE已经被L2分数覆盖”。若要更改目标定义，应显式修改LearningProblem的目标语义。

### 变体二：关注泛化

目的：保留点输出与SGD，在训练集上做参数更新、按验证误差挑选候选。

改在哪里：本章builder保持不变；同时替换它调用的两个工厂，避免只改选择开关却没有验证数据。

替换 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import train_valid_split


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0*X[:, 0] - 0.5*X[:, 1]
    return train_valid_split(
        X, y, valid_ratio=0.25, seed=int(seed),
        feature_names=("x0", "x1"), target_name="output",
    )
```

替换 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedRegressionProblem


def build_problem(data):
    return SupervisedRegressionProblem(data, use_valid_objective=True)
```

行为变化：默认24条样本被切为18条训练、6条验证，第一原始目标来自valid.mse，梯度仍来自训练数据；PointHead和原SGD工厂无需变化。

限制：这不等于在验证集上训练，也不替代最终测试数据。检查best_feedback.signals中的primary_objective与metrics中的valid.mse，不要只看有验证数组就假定它被用于选择。

## mlblack.head.binary_logistic · 二元概率的完整装配

**什么时候用：** 把两特征模型用于二分类，输出类别0/1的两列概率；数据、Head、Problem与搜索方法需要一起接好。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import BinaryLogisticHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=BinaryLogisticHead(classes=(0, 1), temperature=1.0),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = (X[:, 0] - 0.5 * X[:, 1] > 0.0).astype(int)
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="above_boundary",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=False,
        objective_metrics=("log_loss", "error_rate"),
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为3，模型predict_proba(X)返回(n_samples,2)，每行和约为1；predict(X)返回0/1。分类Problem直接从概率argmax计算标签指标，metrics键为train.log_loss/train.error_rate/train.accuracy；它不产生梯度。本章高斯搜索只按第一目标log_loss作比较，不把第二目标error_rate丢出原始反馈。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，最终按log_loss+error_rate之和，非仅log_loss。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 分类Problem当前不提供梯度，不能沿用宿主原来的SGD；本章显式给出高斯搜索工厂。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：改变概率锐度

目的：在模型布局不变时，改变同一logit对应的概率锐度。

改在哪里：`pipeline/model.py` 中，替换已有LinearPointRepresentation的head实参：

```python
head=BinaryLogisticHead(classes=(0, 1), temperature=0.7)
```

行为变化：参数数量仍为3，同一logit会给出不同概率，log_loss也可能变化。

限制：这一行是上方工厂构造器内的实参替换，不是单独挂载代码；temperature是固定配置，不是额外可训练参数。若要把温度也纳入候选，使用下面的ProbabilityCalibrationHead变体。

### 变体二：部署时提高报阳性门槛

目的：改变实际调用模型predict时的判定门槛。

改在哪里：`pipeline/model.py` 中替换同一个head实参：

```python
head=BinaryLogisticHead(classes=(0, 1), threshold=0.7)
```

行为变化：解码模型的 `predict(X)` 使用0.7作为阳性门槛。

限制：当前SupervisedClassificationProblem直接从 `predict_proba` 的argmax计算训练分类指标，并不消费该threshold，所以不能靠这一个字段改变训练期的召回/误报目标。若要“训练时就按0.7门槛评估”，需要扩展LearningProblem的评估规则，并把对应指标作为明确目标；不能在介绍中声称已有该效果。

## mlblack.head.softmax · 三分类的完整装配

**什么时候用：** 把两特征模型用于三个互斥类别，输出0/1/2的三列概率。每类一个基础线性块，合起来是一个9维模型候选，不是三个Solver。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import SoftmaxHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=SoftmaxHead(n_classes=3, classes=(0, 1, 2)),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    score = X[:, 0] - 0.5 * X[:, 1]
    y = np.digitize(score, bins=(-0.3, 0.3))
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="level",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=False,
        objective_metrics=("log_loss", "error_rate"),
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为9，候选被拆成三个3维logit块。模型predict_proba(X)返回(n_samples,3)，每行和约为1；predict(X)返回0/1/2。分类Problem直接从概率argmax计算标签指标，metrics键为train.log_loss/train.error_rate/train.accuracy；默认两个原始目标是[log_loss,error_rate]。本章高斯搜索只用第一目标log_loss作比较，error_rate仍保留在原始反馈中。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，最终按log_loss+error_rate之和，非仅log_loss；F1单目标变体无第二项。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 当前真实宿主默认是点回归；必须替换下方全部相关工厂，而不能只新增一个未被builder调用的Head函数。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：换业务类别名

目的：让概率列对应业务类别编码，而不局限于0/1/2。

改在哪里：`pipeline/model.py` 的Head改成 `SoftmaxHead(n_classes=3, classes=(10, 20, 30))`，`pipeline/main.py` 同步把标签映射为相同编码：

```python
level = np.digitize(score, bins=(-0.3, 0.3))
y = np.asarray((10, 20, 30), dtype=int)[level]
```

行为变化：三列概率依次代表10、20、30，预测标签也返回这些编码。这里的 `np/score` 来自上方同一数据工厂，不是额外全局对象。

限制：当前NumericDataView把标签转换为浮点数，不能直接把字符串low/normal/high塞进该DataView；业务展示名可以在结果展示时用外部字典映射。只改Head标签而不改y会使类别解释不一致。

### 变体二：按F1选择

目的：明确按各类别F1的宏平均值挑选模型，而非只比较log_loss。

改在哪里：在 `problem/__init__.py` 使用以下工厂：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=False,
        objective_metrics=("f1_macro",),
    )
```

行为变化：实现把该指标转换成 `1 - f1_macro` 供最小化，原始 `train.f1_macro` 仍在metrics中。

限制：这个目标不提供梯度，继续使用无梯度搜索；不能把SGD学习率调小当作解决不支持梯度的办法。

## mlblack.head.probability_calibration · 把温度纳入模型参数搜索

**什么时候用：** 在二分类模型的基础参数之外，再搜索一个温度参数，让原始目标直接评估温度变换后的概率。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import ProbabilityCalibrationHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=ProbabilityCalibrationHead(min_temperature=0.05, max_temperature=10.0),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = (X[:, 0] - 0.5 * X[:, 1] > 0.0).astype(int)
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="above_boundary",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=False,
        objective_metrics=("log_loss", "error_rate"),
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为4，模型predict_proba(X)返回(n_samples,2)，每行和约为1；predict(X)返回0/1。分类Problem直接从概率argmax计算标签指标，metrics键为train.log_loss/train.error_rate/train.accuracy；它不产生梯度。本章高斯搜索只按第一目标log_loss作比较，不把第二目标error_rate丢出原始反馈。最后一维是raw temperature，经softplus和边界限制得到实际温度，不应把raw值直接当实际温度。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，最终按log_loss+error_rate之和，非仅log_loss。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 本例同时搜索基础权重与温度；没有冻结一个已训练模型。raw温度参数也不等于模型的实际正温度。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：把校准放在验证数据上衡量

目的：让基础参数与温度的选择依据来自明确留出的验证区域。

改在哪里：保留本章已接通的模型工厂、完整builder及无梯度Adapter，同时替换下面两个工厂：

替换 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import train_valid_split


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = (X[:, 0] - 0.5*X[:, 1] > 0.0).astype(int)
    return train_valid_split(
        X, y, valid_ratio=0.25, seed=int(seed),
        feature_names=("x0", "x1"), target_name="above_boundary",
    )
```

替换 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedClassificationProblem


def build_problem(data):
    return SupervisedClassificationProblem(
        data,
        use_valid_objective=True,
        objective_metrics=("log_loss",),
        positive_label=1,
    )
```

行为变化：搜索器比较第一目标valid.log_loss，训练与验证指标同时保留；本章4维模型仍同时搜索3个基础参数与raw温度。

限制：这不是冻结一个已训练模型只调温度。若要冻结基础模型，需要相应的只调温度Representation或候选生成规则；不能仅设置use_valid_objective就声称基础参数已冻结。

### 变体二：收紧温度范围

目的：限制概率变换的强度。

改在哪里：在 `pipeline/model.py` 的表示构造器内替换head实参：

```python
head=ProbabilityCalibrationHead(min_temperature=0.2, max_temperature=3.0)
```

行为变化：实际温度被约束在0.2到3.0之间，参数维数仍为4。

限制：这改变了候选到概率的解释；更换范围后重新核对目标，不把旧反馈直接当成新规则下的反馈。

## mlblack.head.two_model_interval · 上下界模型与覆盖约束

**什么时候用：** 预测连续目标的上下界，同时考虑覆盖率、区间宽度和漏出距离。上下界各由一个基础线性块生成。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import TwoModelIntervalHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=TwoModelIntervalHead(enforce_order=True),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="output",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data,
        target_coverage=0.9,
        width_weight=1.0,
        miss_weight=10.0,
        use_valid_objective=False,
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为6，模型predict_interval(X)返回等长lower/upper，predict(X)是(n_samples,2)。metrics含train.coverage/train.mean_width/train.mean_miss_distance；原始objectives为[width_weight*width+miss_weight*miss,width,miss]，constraints为[target_coverage-coverage]。高斯搜索按首个区间目标比较，仍须同时检查覆盖约束是否满足。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，默认sum三个目标，非仅首项。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 区间Problem没有梯度；覆盖率目标是数据上的经验要求，不是统计置信保证。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：优先避免漏出

目的：在区间宽度与漏出代价之间，更重视样本落在区间之外的距离。

改在哪里：把 `problem/__init__.py` 的工厂替换为：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data,
        target_coverage=0.9,
        width_weight=1.0,
        miss_weight=30.0,
        use_valid_objective=False,
    )
```

行为变化：第一目标更重视漏出距离，数据、Head布局和Adapter可保持。

限制：该修改不直接保证更高覆盖率，实际还要看constraints和coverage指标。

### 变体二：改为多目标种群搜索

目的：保留区间总目标、宽度、漏出距离之间的多目标竞争。

改在哪里：在原 `adapter/__init__.py` 返回公开NSGA2，保留三个目标的Pareto选择，而不是高斯搜索的第一列聚合：

```python
from nsgablack.adapters import NSGA2Adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return NSGA2Adapter(population_size=8, offspring_size=8)
```

行为变化：模型仍由mlblack表示和Problem解释，NSGA2按候选的多目标反馈作环境选择。

限制：NSGA2只选择语义候选的数值工作投影，不能自己把6维数组切成两个模型。此装配变体依据当前语义候选支持设计，尚未在本轮执行；验收时应核对最终成员的语义token、三个原始目标与约束，并使用真实Pareto/最终成员结果，不把求值历史全部当成最终前沿。

## mlblack.head.interval · 两模型区间Head的直接别名

**什么时候用：** 使用短名称IntervalHead装配同一个两模型区间实现；它是TwoModelIntervalHead的直接别名，不是又一套区间算法。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import IntervalHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=IntervalHead(enforce_order=True),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="output",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data,
        target_coverage=0.9,
        width_weight=1.0,
        miss_weight=10.0,
        use_valid_objective=False,
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为6，模型predict_interval(X)返回等长lower/upper，predict(X)是(n_samples,2)。metrics含train.coverage/train.mean_width/train.mean_miss_distance；原始objectives为[width_weight*width+miss_weight*miss,width,miss]，constraints为[target_coverage-coverage]。高斯搜索按首个区间目标比较，仍须同时检查覆盖约束是否满足。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，默认sum三个目标，非仅首项。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 不用同时装配IntervalHead与TwoModelIntervalHead；两者是同一类。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：复用同一实现的扩展点

目的：用较重的漏出代价探索另一个区间折中，同时保留短名称Head。

改在哪里：Head仍用IntervalHead，`problem/__init__.py` 改为：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data, target_coverage=0.9, miss_weight=30.0,
        use_valid_objective=False,
    )
```

行为变化：与TwoModelIntervalHead节的同名变体完全相同，改变的是目标折中，不是别名的实现。

限制：这个变体只改目标权重，不会把lower/upper坐标变成center/radius。需要中心与半径解释时应显式使用CenterRadiusIntervalHead并重新求值，不能给别名加一个不存在的模式参数。

## mlblack.head.center_radius_interval · 中心与非负半径的区间模型

**什么时候用：** 将区间解释为中心预测加减非负半径，分别解释位置与幅度；仍由区间Problem衡量覆盖、宽度和漏出。

**先准备什么：** 使用mlblack仓库已有的 `examples/cases/catalog_codec_demo/`，其中默认组只运行 `cases/linear_point/`。先确认blackbase、nsgablack、mlblack与NumPy可导入；不需要Torch、GPU或模型API。该Case已经有 `config.py::DEFAULTS`，字段为seed17、n_samples24、max_steps3、learning_rate0.05；保留这个配置文件。下文路径中的Case均指这个 `linear_point`，不要把代码放在项目根目录。 当前宿主实际默认是点回归和SGD；本节明确把它改为当前任务，下面所有替换都必须完成，不能只新增Head工厂或假定已经存在无梯度Adapter。

**放在哪：** 先替换Case的规范 `build_solver.py`，再按本节代码新建或替换 `pipeline/model.py`。现有 `pipeline/__init__.py` 已从main导出build_pipeline，保持该导出；builder会显式导入并调用新的模型工厂，不会因为文件存在就自动启用它。`resource_context` 是Project传入的授权，装配代码不自行申请资源。 本章前五个基础代码块依次对应build_solver.py、pipeline/model.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py，必须按这些路径分别保存；不需要把五块合成一个文件。

1. Case的完整 `build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .pipeline.model import build_representation
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(
        seed=settings["seed"],
        n_samples=settings["n_samples"],
    )
    solver = build_learning_solver(
        problem=build_problem(data),
        representation=build_representation(data, seed=settings["seed"]),
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context,
        run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

2. 新建或替换Case的 `pipeline/model.py`：

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import CenterRadiusIntervalHead


def build_representation(data, *, seed):
    return LinearPointRepresentation(
        LinearPointConfig(
            n_features=data.n_features,
            feature_names=data.effective_feature_names,
            random_seed=int(seed),
        ),
        head=CenterRadiusIntervalHead(radius_transform="softplus"),
    )
```

3. 替换Case的 `pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView


def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return NumericDataView(
        X_train=X, y_train=y,
        feature_names=("x0", "x1"), target_name="output",
    )
```

4. 替换Case的 `problem/__init__.py`：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data,
        target_coverage=0.9,
        width_weight=1.0,
        miss_weight=10.0,
        use_valid_objective=False,
    )
```

5. 替换Case的 `adapter/__init__.py`，明确切到无梯度搜索：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter(*, learning_rate):
    del learning_rate
    return build_optimization_adapter(
        "search.random_gaussian",
        population_size=8,
        mutation_scale=0.15,
        random_seed=17,
        objective_aggregation="first",
    )
```

这里保留learning_rate形参是为了匹配本章builder的现有调用，它在这个搜索方法中被明确忽略；实际变化尺度是mutation_scale。选择只比较第一原始目标，不能把它描述成完整Pareto搜索。

**接入步骤：** 先核对本章列出的所有文件，再从正式Project入口运行。builder先取得DataView，再构造带Head的模型表示、Problem和Adapter；运行中Adapter提出参数候选，表示将UnknownState解释成模型，Problem用数据生成原始反馈，Adapter按自己的规则消费反馈并选择后继，Solver负责接纳、事务提交和逻辑步计数。装配、观察和读取dimension不应提前调用init或构建算法Unit。

**怎样判断接对：** 表示dimension应为6，模型predict_interval(X)返回等长lower/upper，predict(X)是(n_samples,2)。metrics含train.coverage/train.mean_width/train.mean_miss_distance；原始objectives为[width_weight*width+miss_weight*miss,width,miss]，constraints为[target_coverage-coverage]。高斯搜索按首个区间目标比较，仍须同时检查覆盖约束是否满足。 在保留同一次正式Case实例的程序式调用中，solver.fit()/run()返回TrainerResult；从result.best_model读取模型，result.best_feedback读取反馈，result.best_state读取参数，result.report读取ML报告。这里的solver/result是实际运行实例及其返回值，不是装配时凭空预建的对象。默认Project终端摘要不保证打印这些完整对象；不要为了读取它们再次不加区分地运行一次训练。 权威结果：result.best_state/best_model/best_feedback来自Solver权威incumbent，不等于Adapter最后后继或最终成员；局部objective_aggregation不自动配置Solver最终scalarizer。本例未显式配置scalarizer，默认sum三个目标，非仅首项。

**运行入口：** 从mlblack仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 核对实际装配，再执行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。保留Project原有1线程CPU配置与默认组；本节不需要新增stage、全局资源分配器或第二个运行循环。本页只显示命令，本轮未执行这些改造。

**边界：** 虽然同样是6维，它的坐标是center/raw_radius，与lower/upper布局语义不同；旧状态不能直接换解释。 3个逻辑步只是小预算接线演示，不保证训练收敛或效果优于其它配置。更换参数布局时应新建运行或使用匹配的正式恢复协议，不能复用旧数组反馈冒充新模型。

**接口依据与验证状态：** `examples/cases/catalog_codec_demo/cases/linear_point/`；`representations/linear_point.py`、`representations/codecs/linear.py`、`representations/heads/`、`problems/supervised.py`、`problems/classification.py`、`integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`及nsgablack对应Adapter实现。源码核对，未执行改造后的Case。

### 变体一：半径用绝对值

目的：使用绝对值解释第二个基础模型预测的raw radius。

改在哪里：在 `pipeline/model.py` 替换head实参：

```python
head=CenterRadiusIntervalHead(radius_transform="abs")
```

行为变化：负raw radius按绝对值变成半径，布局仍为6维。

限制：同一参数对应的实际区间会改变，需要重新求值，不能沿用旧反馈。

### 变体二：对保守区间提出更明确的要求

目的：提高经验覆盖率要求，并明确漏出所对应的目标代价。

改在哪里：在 `problem/__init__.py` 使用以下工厂，Head保持不变：

```python
from mlblack.problems import SupervisedIntervalRegressionProblem


def build_problem(data):
    return SupervisedIntervalRegressionProblem(
        data,
        target_coverage=0.95,
        width_weight=1.0,
        miss_weight=20.0,
        use_valid_objective=False,
    )
```

行为变化：经验覆盖约束收紧，第一目标同时更重视漏出距离。

限制：Head仅负责构造区间，不会自行把覆盖率变成0.95。验收应同时看覆盖约束、宽度和漏出指标，避免只报告一个总分。

## 这些应用怎样继续延拓

换方法、换数据切分、换输出Head、换目标和约束，分别对应不同工厂。先明确你希望改变的行为，再改真正负责该行为的组件。例如“降低误报”不能只凭Head名字决定要改哪里；先确认你是改预测标签门槛、训练选择指标，还是加入业务代价约束。“区间更保守”也要看覆盖约束和宽度代价，而不是把radius数组随意放大后沿用原评分。

本页基础Project只承担一个ML Case。与其它Case串行/并行、把训练作为外层优化的内层任务，仍走共享Project/Case/L0与正式结果引用；不用为了延拓一个Head复制新的训练循环。新应用经真实Case验证后，可以把代码位置、条件、实际结果和源码版本一起保存在目录知识中；没有执行的变体保持“设计/源码核对”状态。

公开键映射：`mlblack.integration.learning_solver` 与 `mlblack.trainer.learning_solver` 是同一类；`mlblack.head.interval` 与 `mlblack.head.two_model_interval` 是同一类。`mlblack.codec.linear_point` 和 `mlblack.representation.linear_point` 则职责不同：前者是基础参数布局，后者是带Head的模型表示，不能因名称相似而合成一个组件。
