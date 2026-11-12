# 小型文本与图像对比：输入含义要随任务一起装配

以下是可编辑的正式 Case 接线，只有源码/语法/来源核对，没有训练、加载预训练模型或下载。两项使用不同完整 Project 副本；CPU PyTorch 是实际可选依赖，不以目录条目替代依赖安装。

## neural.text · 只用训练文本建词表，分类与下一词预测显式切换

**什么时候用：** 用本地小词表验证文本输入、任务 Problem、神经图和发布语义，而不是训练大语言模型。实际使用 VocabularyTokenizer、TokenizedTextDatasetBuilder、TinyTransformerClassificationProblem；LM 变体使用 TinyTransformerLanguageModelProblem。

**先准备什么：** 当前三仓、NumPy、CPU torch>=2.0。完整复制 `mlblack/examples/cases/tiny_transformer_smoke`，只改 `cases/tiny_transformer_classification` 作宿主。所有句子恰好4个简单英文token，无padding；验证文本不会参与词表fit。保留Project L0/Case别名/规范入口，新增单Case组避免默认组启动其它训练。

**放在哪：** 替换宿主 config.py、pipeline/main.py、problem/__init__.py 和 build_solver.py。保留 pipeline 包既有 build_data 导出；原preset builder被本页显式正式装配取代，未调用的目录不代表启用了旧Problem。另保存下节的Project组/结果薄入口。

**接入步骤：** 先创建训练专属Builder，再用同一个已拟合tokenizer变换独立验证文本。

```python
# cases/tiny_transformer_classification/config.py
MODE = "classification"
```

```python
# cases/tiny_transformer_classification/pipeline/main.py
import numpy as np
from mlblack.pipeline import NumericDataView, TokenizedTextDatasetBuilder, TokenizedTextDatasetConfig
from mlblack.pipeline.numericizer import VocabularyTokenizer, VocabularyTokenizerConfig

def build_data():
    train = [dict(text="red small square now", label=0),
        dict(text="blue large round now", label=1),
        dict(text="red large round now", label=0),
        dict(text="blue small square now", label=1)]
    valid = [dict(text="red small round now", label=0),
             dict(text="blue large square now", label=1)]
    tokenizer = VocabularyTokenizer(VocabularyTokenizerConfig(max_length=4,
        add_bos=False, add_eos=False, lowercase=True))
    if any(len(tokenizer.tokenize(row["text"])) != 4 for row in train+valid):
        raise ValueError("this recipe requires four real tokens, no silent padding/truncation")
    builder = TokenizedTextDatasetBuilder(tokenizer, TokenizedTextDatasetConfig(
        text_column="text", target_column="label", max_length=4, valid_ratio=0.))
    prepared = builder.from_rows(train)
    validation_ids = tokenizer.transform([row["text"] for row in valid])
    data = NumericDataView(X_train=prepared.X_train, y_train=prepared.y_train,
        X_valid=validation_ids, y_valid=np.array([row["label"] for row in valid]),
        feature_names=prepared.feature_names, metadata=dict(prepared.metadata))
    return data, tokenizer
```

Builder 对 VocabularyTokenizer 调 fit_transform 后才按 valid_ratio 划分；若直接传全量文本再设 valid_ratio，验证词会进入词表。本例先分开、valid_ratio=0，仅训练记录进入Builder。它返回的metadata只有tokenizer描述，**不是完整词表**；下面Artifact hook额外保存as_dict。未知词映射到unk，默认encode会截断/填pad；本例显式检查4词，不能据此推广成无截断保证。

```python
# cases/tiny_transformer_classification/problem/__init__.py
from dataclasses import replace
from mlblack.problems import TinyTransformerClassificationProblem, TinyTransformerLanguageModelProblem

class TextClassification(TinyTransformerClassificationProblem):
    def __init__(self, data, tokenizer):
        super().__init__(data)
        self.tokenizer = tokenizer
    def build_model_artifact(self, model, context=None):
        value = super().build_model_artifact(model, context)
        return replace(value, metadata={**dict(value.metadata),
            "tokenizer": self.tokenizer.as_dict()})

class TextLM(TinyTransformerLanguageModelProblem):
    def __init__(self, data, tokenizer):
        super().__init__(data)
        self.tokenizer = tokenizer
    def build_model_artifact(self, model, context=None):
        value = super().build_model_artifact(model, context)
        return replace(value, metadata={**dict(value.metadata),
            "tokenizer": self.tokenizer.as_dict()})

def build_problem(data, tokenizer, mode):
    if mode == "classification":
        return TextClassification(data, tokenizer)
    if mode == "lm":
        return TextLM(data, tokenizer)
    raise ValueError("unknown text task")
```

## neural.text.wiring · Head、损失、模型引用与正式入口

接上节同一Case继续保存。训练与验证都保留同一token ID含义，不能恢复时重新fit另一份词表。

```python
# cases/tiny_transformer_classification/build_solver.py
from mlblack.integrations.nsgablack_gradient import build_gradient_trainer
from mlblack.representations import NeuralGraphRepresentation
from nsgablack.project import apply_solver_component_overrides
from .config import MODE
from .pipeline.main import build_data
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit explicit text task config")
    data, tokenizer = build_data()
    size = len(tokenizer.vocab)
    if MODE == "classification":
        head = {"kind": "classification", "name": "classification", "params": {"num_classes": 2}}
        maximum = 4
    elif MODE == "lm":
        head = {"kind": "language_modeling", "name": "lm", "params": {"vocab_size": size}}
        maximum = 3
    else:
        raise ValueError("unknown text task")
    representation = NeuralGraphRepresentation.tiny_transformer(vocab_size=size,
        max_length=maximum, hidden_dim=8, num_layers=1, num_heads=2,
        heads=(head,), random_seed=17)
    solver = build_gradient_trainer(problem=build_problem(data, tokenizer, MODE),
        representation=representation, method="gradient.adamw", compute_backend="torch",
        learning_rate=.01, resource_context=resource_context, run_name="text_"+MODE)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(2)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

分类输入4个token，Head输出二分类logits，Problem用y标签交叉熵；LM将每个4-token序列的前三个送模型，后三个作逐位置目标，所以模型max_length=3，data.y的类别不参与LM损失。当前这个LM路径不支持本例之外任意padding监督mask，不等于仅训练assistant回复的SFT。

在原 project_config.py 末尾追加，保留L0：

```python
STAGES.append(dict(name="catalog_text", cases=["tiny_transformer_classification"], policy="serial",
    resource_requests={"tiny_transformer_classification": dict(threads=1, device="cpu", backend="local")}))
GROUPS["catalog_text"] = dict(stages=["catalog_text"])
```

Project根保存 `run_text_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="catalog_text")
    case = next(c for c in run.case_results if c.request.case_name == "tiny_transformer_classification")
    case.raise_for_failure()
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise ValueError("evaluated feedback/model required")
    payload = {"run_id": run.run_id, "objectives": result.best_objectives.tolist(),
        "metrics": dict(result.best_feedback.metrics), "signals": dict(result.best_feedback.signals),
        "model_ref": result.best_model_ref.as_dict()}
    path = root / "results" / "text.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 当前分类单目标valid.log_loss，train/valid还有accuracy/error_rate；LM变体单目标valid.cross_entropy，另有train/valid.perplexity，不能把两个任务的数直接比性能。训练梯度来自训练集，验证只用于目标/观测。正式NeuralGraphArtifact保留图/布局/Head/audit及完整tokenizer，模型载荷NPZ与best_model_ref走原finalization；不直接返回活Tokenizer/Module跨进程。LM audit同样右裁一位以匹配3-token模型。它不保证有通用推理加载器或语言能力。

**运行入口：** 副本根先 `python run_project.py --group catalog_text --check --build-check`，再 `python run_text_and_report.py`。后者实际训练一次正式Case，本文未执行；不去运行默认三个Case来补报告。JSON为观察副本，检查新run_id和正式Case状态。

### 变体一：同一词表数据改为下一token任务

**目的：** 改变真实监督语义而不是只改一个展示标签。

**改在哪里：** 完整替换宿主config.py。

```python
MODE = "lm"
```

**行为变化：** Builder/Tokenizer保留，Head与Problem/max_length共同切换；类别y被LM忽略。**限制：** 只用四条合成句子、两步预算，无预训练，不保证生成能力；分类模型checkpoint和LM Head布局不同，不能混用。

源码：`mlblack/pipeline/numericizer/text.py`、`pipeline/datasets.py::TokenizedTextDatasetBuilder`、`representations/neural_graph.py`、`problems/neural.py`、`backends/torch_neural/capabilities/losses.py`、`core/artifact_provider.py`。

## neural.contrastive · “Pair”数据对象实际承载三个对齐图像

**什么时候用：** 用anchor/positive/negative三元组学习检索embedding，不是图像分类，也不是只有两张图就能自动生成负样本。

**先准备什么：** 三仓、NumPy、CPU PyTorch。复制完整 `mlblack/examples/cases/benchmarks`，只改其中 `benchmark_tiny_cnn_contrastive` Case；保留L0/标准入口。三数组相同NCHW布局 `(4,1,4,4)`，不需要标签；配对关系由使用者明确提供。

**放在哪：** 完整替换该Case pipeline/main.py和build_solver.py，新建config.py；保留pipeline包build_data导出。追加单Case组和Project报告薄入口。原Problem工厂不再由新builder调用，preset创建实际TinyCNNImageContrastiveProblem。

**接入步骤：** 先保存margin配置，再构造真实三元组。

```python
# cases/benchmark_tiny_cnn_contrastive/config.py
MARGIN = .5
```

```python
# cases/benchmark_tiny_cnn_contrastive/pipeline/main.py
import numpy as np
from mlblack.pipeline import ImageContrastivePairDataView

def build_data():
    a = np.zeros((4, 1, 4, 4), dtype=float)
    a[:, :, :2, :2] = 1.
    p = a * .9
    n = np.zeros_like(a)
    n[:, :, 2:, 2:] = 1.
    return ImageContrastivePairDataView(anchor_train=a, positive_train=p, negative_train=n)
```

```python
# cases/benchmark_tiny_cnn_contrastive/build_solver.py
from mlblack.presets import build_tiny_cnn_image_contrastive_trainer
from nsgablack.project import apply_solver_component_overrides
from .config import MARGIN
from .pipeline.main import build_data

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit explicit contrastive config")
    solver = build_tiny_cnn_image_contrastive_trainer(build_data(), conv_channels=(4,),
        embedding_dim=4, margin=MARGIN, kernel_size=3, compute_backend="torch",
        learning_rate=.01, random_seed=17, resource_context=resource_context,
        run_name="contrastive_case")
    solver.set_max_steps(2)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

ImageContrastivePairDataView检查三数组shape相等，没有验证集字段、自动negative mining或类别语义。preset实际创建TinyCNN/retrieval Head，embedding_dim=4是输出向量维数；Problem将三组图分别前向，并计算triplet margin loss，不把正负距离当两个独立目标。结果仍由共享Gradient Adapter/Provider处理。

追加Project单Case组：

```python
STAGES.append(dict(name="catalog_contrastive", cases=["benchmark_tiny_cnn_contrastive"], policy="serial",
    resource_requests={"benchmark_tiny_cnn_contrastive": dict(threads=1, device="cpu", backend="local")}))
GROUPS["catalog_contrastive"] = dict(stages=["catalog_contrastive"])
```

Project根保存 `run_contrastive_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="catalog_contrastive")
    case = next(c for c in run.case_results if c.request.case_name == "benchmark_tiny_cnn_contrastive")
    case.raise_for_failure()
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise ValueError("evaluated contrastive result required")
    payload = {"run_id": run.run_id, "objectives": result.best_objectives.tolist(),
        "metrics": dict(result.best_feedback.metrics), "model_ref": result.best_model_ref.as_dict()}
    path = root / "results" / "contrastive.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 单目标为训练triplet loss；看train.triplet_loss、train.positive_distance、train.negative_distance、train.retrieval_accuracy。此accuracy只检查每个正距离小于负距离，不检查差值达到margin。距离实现是embedding各维平方差的均值。没有valid指标时不能声称泛化或召回率已验收。正式NeuralGraphArtifact记录retrieval语义/图布局，Torch载荷NPZ与模型引用按原finalization发布。零loss只说明这些已给定三元组满足margin，不表示全库检索正确。

**运行入口：** 副本根先 `python run_project.py --group catalog_contrastive --check --build-check`，再 `python run_contrastive_and_report.py`；后者会训练，本轮未执行。核对新run_id/Case状态，本地JSON不是额外权威收据。

### 变体一：改变要求的间隔

**目的：** 只改triplet间隔，保留数据与网络。

**改在哪里：** 完整替换config.py。

```python
MARGIN = 1.
```

**行为变化：** loss用更大间隔衡量同一embedding；旧小间隔满足不代表新配置满足，retrieval_accuracy的正负排序定义不变。**限制：** 不自动构造更难负样本，不能把这一参数改变解释成提升真实召回率。

源码：`mlblack/pipeline/data_views/contrastive.py`、`presets/neural.py`、`problems/neural.py::TinyCNNImageContrastiveProblem`、Torch `capabilities/losses.py`、`core/artifact_provider.py`。
