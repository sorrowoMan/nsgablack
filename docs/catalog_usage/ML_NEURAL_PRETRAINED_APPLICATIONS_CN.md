# 预训练与结构搜索：可以装的路径、必须明确的边界

本书没有加载权重、运行训练、下载、调用模型API或外部数据库。已有本地模型和可选依赖是运行前提，不会代替用户自动获取。HF SFT 有正式 Case；通用桥和旧结构搜索 Problem 的缺口单列为迁移说明，不冒称它们已接通任意 Case。

## neural.hf_sft · 一次完整有限fit，交付LoRA包

**什么时候用：** 已经有兼容的本地 HuggingFace causal LM、tokenizer/chat_template 和实际目标模块名，希望把一次有限PEFT LoRA fit放入统一Project/Case/Artifact链。不是在线目录整理，也不会自动替换DeepSeek。

**先准备什么：** 完整复制 `mlblack/examples/cases/framework_assistant_sft`；保留Project原CPU默认L0、assistant_sft Case和运行入口。准备可读取本地HF目录，显式设置 MLBLACK_SFT_MODEL_PATH 与 MLBLACK_SFT_TARGET_MODULES；target_modules必须在这个基座里真实存在。可选依赖为mlblack[sft]所声明的Torch、transformers、PEFT、accelerate、safetensors；本例不启用4bit/CUDA。以下只有机制输入，不是足以改善框架能力的训练集。

**放在哪：** 完整替换 `cases/assistant_sft/config.py` 与 build_solver.py；将下面JSONL保存到该Case既有pipeline/example.jsonl。Project根新增run_sft_and_report.py。资源保持来自正式Project，不向Provider硬塞设备授权。

**接入步骤：** 配置只允许现成本地目录；模型与模块名缺失时明确报错，不猜模型族、不下载。

```python
# cases/assistant_sft/config.py
import os
from pathlib import Path

def settings():
    model = Path(os.environ["MLBLACK_SFT_MODEL_PATH"]).resolve(strict=True)
    if not model.is_dir():
        raise ValueError("model must be a prepared local HF directory")
    modules = tuple(x.strip() for x in os.environ["MLBLACK_SFT_TARGET_MODULES"].split(",") if x.strip())
    if not modules:
        raise ValueError("actual LoRA target modules required")
    return dict(model_name_or_path=str(model),
        dataset_path=str(Path(__file__).parent / "pipeline" / "example.jsonl"),
        max_length=512, optimizer_steps=1, batch_size=1, learning_rate=2e-4,
        target_modules=modules, label_mode="completion", local_files_only=True,
        load_in_4bit=False, seed=17)
```

```json
{"id":"local-mechanism-only","messages":[{"role":"user","content":"Unit移除成员是否应当删除母池的解？"},{"role":"assistant","content":"解除这个Unit的成员关系即可。其他Unit、子池和历史仍可能引用同一候选版本，不应因此删除池中的候选。这只是输入格式例子。"}]}
```

```python
# cases/assistant_sft/build_solver.py
from mlblack.integrations.hf_sft import HFSFTConfig, build_hf_sft_solver
from .config import settings

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("edit explicit SFT settings instead of overriding the local-file boundary")
    options = settings()
    dataset = options.pop("dataset_path")
    return build_hf_sft_solver(HFSFTConfig(**options), dataset, resource_context=resource_context)
```

正规工厂使用FixedCandidateAdapter：候选是一维fit请求，base模型/optimizer/tokenizer留在HFSFTProvider，不展开成搜索参数。一个Solver评估是一次完整fit；optimizer_steps=1是fit内部的优化次数，不是Solver generation。加载/训练只在实际评估发生；构造会读取并固定数据摘要，但不加载HF模型。

可在副本根新增以下纯文件预检入口 `inspect_sft.py`，不与正式训练混为一谈：

```python
import json
from mlblack.integrations.hf_sft import HFSFTConfig, preflight_hf_sft
from cases.assistant_sft.config import settings

def main():
    values = settings()
    dataset = values.pop("dataset_path")
    report = preflight_hf_sft(HFSFTConfig(**values), dataset)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_to_attempt"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
```

文件预检仅看会话格式、包可发现性与目录，不加载tokenizer，所以token_length_checked=False。真实completion模式要求generation prompt token是完整对话的精确前缀；过长、无监督token或模板不相容会拒绝，不默默截断，不承诺512一定足够。

Project根保存完整 `run_sft_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(c for c in run.case_results if c.request.case_name == "assistant_sft")
    case.raise_for_failure()
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise ValueError("completed fit feedback and published adapter bundle required")
    payload = {"run_id": run.run_id, "objectives": result.best_objectives.tolist(),
        "metrics": dict(result.best_feedback.metrics),
        "model_ref": result.best_model_ref.as_dict()}
    path = root / "results" / "sft.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 正式单目标等于训练step平均loss，metrics包含training_loss/optimizer_steps，不是验证表现或框架认知指标。正式TypedModelArtifact载荷为完成后的LoRA ZIP：PEFT增量权重、tokenizer和manifest，不含基座全量权重。发布只在完整finalization成功后生效，取消/失败不交付半包。best_model_ref是原Case发布引用，sft.json只是观察副本。

**运行入口：** 提供实际环境变量后，在副本根先 `python inspect_sft.py`，再 `python run_project.py --check --build-check`；决定进行训练时才运行 `python run_sft_and_report.py`。本轮均未执行。当前机器没有所需本地基座/模块名时应停在明确的输入缺失，不把空结果写成完成。普通CPU也可能因模型太大不可用，不从目录存在推断资源足够。

### 变体一：同一个完整fit做两个内部优化step

**目的：** 区分外部优化器内步数与框架逻辑提交。

**改在哪里：** config.py保留上面的settings定义，最后追加以下完整覆盖：

```python
_single_step_settings = settings

def settings():
    return {**_single_step_settings(), "optimizer_steps": 2}
```

**行为变化：** 仍一次fit/一次Solver评估，但内部AdamW进行2步；训练消耗增加。**限制：** 不能逐内部step回滚、不能恢复正在进行的optimizer。完成状态可由原Provider/正式checkpoint恢复，恢复投影不再fit；显式追加一个逻辑step表示另一次完整训练，不是只读加载。

源码：`mlblack/integrations/hf_sft.py`、`pipeline/conversation_sft.py`、现有framework_assistant_sft Project的README/配置。这里只说明机制，没有模型质量或本轮运行收据。

## neural.pretrained.bridges · 三个桥的可用操作与未闭合的Case交接

**什么时候用：** 已有本地tokenizer/模型或checkpoint，要做显式转换。三个桥不是一个“随便塞入任意Adapter”的模型组件，本节是迁移/集成边界说明。

**先准备什么：** transformers与PyTorch可选依赖、真实本地HF文件、目标模型及明确张量名/形状。加载不是零成本；不应由Catalog刷新或Doctor为了检查而触发。两种bridge kwargs必须显式local_files_only=True；默认配置本身没有替你限制所有联网路径。

**放在哪：** 放在已授权运行的Provider/Case本地数据准备边界；活对象不放共享context或checkpoint。本节只提供独立配置/映射工具的完整操作，不冒称已存在兼容全部模型的正式Problem/Provider/Codec。正式HF LoRA训练优先走上一节现有Case；本地小模型任务可走本目录文本/图像正式配方。

**接入步骤：** 以下工厂只构造惰性桥并返回描述；不调用load/encode/generate，因此它不证明文件、模板或模型已可运行。

```python
from pathlib import Path
from mlblack.integrations.transformers_bridge import (
    PretrainedTokenizerBridge, PretrainedTokenizerBridgeConfig,
    PretrainedModelBridge, PretrainedModelBridgeConfig,
)

def local_bridges(model_directory, *, device="cpu"):
    path = Path(model_directory).resolve(strict=True)
    if not path.is_dir():
        raise ValueError("prepared local HF directory required")
    kwargs = {"local_files_only": True, "trust_remote_code": False}
    tokenizer = PretrainedTokenizerBridge(PretrainedTokenizerBridgeConfig(
        model_name_or_path=str(path), max_length=16, kwargs=kwargs))
    model = PretrainedModelBridge(PretrainedModelBridgeConfig(
        model_name_or_path=str(path), task="causal_lm", device=device, kwargs=kwargs))
    return tokenizer, model, {"tokenizer": tokenizer.describe(), "model": model.describe()}
```

真正调用tokenizer.encode(texts)才load并产出input_ids/attention_mask等NumPy值；模型forward/generate接收后端需要的tensor kwargs，不会自动把上述NumPy字典转设备，也不会帮你定义loss/labels。device在正式Case中必须取自有效ResourceContext，而不是用户随意写cuda绕过L0。缺padding token的tokenizer也不会被桥自动修复。

CheckpointMapper的独立操作可用下面已知三参数线性目标说明，不需HF下载。代码供用户在获准的本地转换任务中执行；本轮没有构造Torch模型或运行映射：

```python
import torch
from mlblack.integrations.transformers_bridge import (
    PretrainedCheckpointMapper, PretrainedCheckpointMappingConfig,
)

def map_known_linear_checkpoint():
    target = torch.nn.Linear(2, 1)
    source = {"proj.weight": torch.tensor([[1., 2.]]), "proj.bias": torch.tensor([.5])}
    mapper = PretrainedCheckpointMapper(PretrainedCheckpointMappingConfig(
        name_map={"weight": "proj.weight", "bias": "proj.bias"},
        allow_shape_match=False, strict_shapes=True, missing_policy="error"))
    report = mapper.map_state_dict(source, target)
    if report.missing or report.shape_mismatch or report.mapped_fraction != 1.:
        raise ValueError("mapping is not complete")
    return target, mapper.flat_values_from_model(target), report.as_dict()
```

**怎样判断接对：** 报告matched列目标名/源名，mapped_fraction按state_dict元素数统计，missing/shape_mismatch必须检查。strict_shapes=True遇到形状不符**保留目标旧值并记录**，不是自动抛错；上方调用者检查拒绝后，target已经经历load_state_dict，不能把该工具误当框架事务。flat_values只按parameters迭代，不含buffer，顺序不自动等于任意NeuralGraphCodec布局。map_bridge会先load源模型，不能在只读预检误调用。

**运行入口：** 本地Python配置/转换模块可调用上述函数，不执行Solver；正式训练调用上一节Project命令。当前缺少“任意HF checkpoint→目标神经布局→携带身份的池候选→模型Artifact”的统一端到端映射契约，所以不提供伪装可运行的通用Case。使用时必须为具体模型补齐目标语义、布局验证、资源绑定与发布路径。

### 变体一：缺失源字段时仅作诊断

**目的：** 明确保留目标旧值的语义，不把部分映射当完整迁移。

**改在哪里：** 新增配置工厂，在实际转换脚本创建Mapper时显式使用它：

```python
def diagnostic_mapper():
    return PretrainedCheckpointMapper(PretrainedCheckpointMappingConfig(
        name_map={"weight": "proj.weight", "bias": "proj.bias"},
        allow_shape_match=False, strict_shapes=True, missing_policy="keep_target"))
```

**行为变化：** 缺字段不立刻抛错，报告保留missing，目标仍含旧参数。**限制：** 诊断不构成完整模型交付，更不能以shape相同推断语义等价；此变体没有把三桥接成正式运行器。

## neural.transformer.space · 结构向量的可用解读，不隐式训练

**什么时候用：** 需要在装配前看清8维结构向量分别控制什么；TransformerSpecSearchSpace是模型结构映射，不是参数训练或池Unit。

**先准备什么：** 当前三仓与NumPy，读取结构不需Torch计算或HF权重。本例固定classification任务、vocab8/max_length4，输出的Spec可交给正式NeuralGraphRepresentation；数据词表/任务Head仍须匹配。

**放在哪：** Case的pipeline/结构工厂或本地配置诊断模块。下面函数只返回普通Spec描述，不启动搜索、内层fit或资源授权。

**接入步骤：** 调用者先校验长度、有限数和区间，避免旧映射器默默补零短向量或取abs处理负数。

```python
import numpy as np
from mlblack.integrations.nsgablack_neural import TransformerSpecSearchConfig, TransformerSpecSearchSpace

def read_transformer_spec(values):
    a = np.asarray(values, dtype=float).reshape(-1)
    if a.size != 8 or not np.all(np.isfinite(a)) or np.any((a < 0.) | (a > 1.)):
        raise ValueError("eight finite structural coordinates in [0,1] required")
    config = TransformerSpecSearchConfig(task="classification", vocab_size=8, max_length=4,
        num_classes=2, hidden_dim_choices=(8, 16), num_layer_choices=(1, 2),
        num_head_choices=(1, 2), ffn_ratio_choices=(2., 4.),
        norm_choices=("layer_norm", "rms_norm"), position_choices=("learned", "rope"),
        ffn_kind_choices=("mlp", "swiglu"), lora_rank_choices=(0, 2))
    spec = TransformerSpecSearchSpace(config).decode(a)
    return spec.as_dict()

description = read_transformer_spec(np.zeros(8))
```

坐标依次选hidden/layers/heads/ffn ratio/norm/position/ffn kind/LoRA rank；heads会过滤为能整除hidden_dim的候选。每维选择实现为`int(abs(value)*len(choices)) % len(choices)`，所以1回到首选，不是上端最后一项；不能当连续单调几何参数。描述中的LoRA是tiny图规格，不是HF PEFT包。

**怎样判断接对：** 全零选择8维hidden、1层、1头、ratio2、layer_norm、learned、mlp、LoRA关闭；描述的Head为classification/2类。仅得到结构描述，没有训练loss、Artifact或L0授权；不能把返回字典当TrainerResult。

**运行入口：** 本地Python调用该完整函数进行配置检查；实际模型计算回到本目录ML_NEURAL_TEXT_VISION_APPLICATIONS的正式Case，在builder构造匹配NeuralGraphRepresentation/Problem。这个结构读取操作不需要新Project或训练循环，本轮未执行它。

### 变体一：查看另一种结构选择

**目的：** 观察离散结构映射。**改在哪里：** 在同一诊断模块追加：

```python
alternative = read_transformer_spec(np.full(8, .75))
```

**行为变化：** 选择16维hidden、2层、2头、ratio4、rms_norm/rope/swiglu及LoRA rank2。**限制：** 更大或有LoRA不表示质量更好；新图和权重布局必须匹配，不能按数值相近复用旧模型。

## neural.transformer.legacy_problem · 原结构搜索Problem的正式嵌套缺口

**什么时候用：** 评估是否能直接把TransformerSpecSearchProblem当“已有正式内Case”的外层搜索问题。本节是迁移说明；现有实现有直接内层fit，不满足当前统一Case交接要求。

**先准备什么：** 阅读`integrations/nsgablack_neural/transformer_spec_search.py`和AGENTS跨框架规则。已有源码测试只能说明旧调用曾被覆盖，不能证明当前路径具备CaseRuntime/子L0/Artifact收据交接。

**放在哪：** 结构解码仍可放pipeline；真实外层评估应通过正式内Case，而不是在旧evaluate_detailed里再补一个私有runner。

**接入步骤：** 只查看声明，不调用evaluate/evaluate_detailed。下面完整函数不执行训练：

```python
from mlblack.integrations.nsgablack_neural import TransformerSpecSearchConfig, TransformerSpecSearchSpace

def explicit_inner_contract():
    config = TransformerSpecSearchConfig(task="classification", vocab_size=8,
        max_length=4, inner_steps=1)
    return {"structural_dimension": TransformerSpecSearchSpace.dimension,
        "declared_inner_steps": config.inner_steps,
        "evaluation_surface": "requires formal child Case integration",
        "execution_verified": False}
```

当前evaluate_detailed直接创建tiny trainer并调用fit；resource_context在构造后set给trainer，不经CaseRuntime.invoke派生子grant；结果从内存report读取复杂度，没有正式子Case请求与模型发布收据链。因此本轮不提供“直接装上就完成嵌套”的示例，也不悄悄执行这个入口。

**怎样判断接对：** 迁移完成的判断应是：外层结构候选有稳定解释；内Case明确消费graph spec、数据与预算；CaseRuntime.invoke给出子grant/取消/结果；外层从正式TrainerResult提取目标和模型引用。单纯返回两数字不是完成标志。

**运行入口：** 当前此旧条目只作源码参考，不运行evaluate。已有正式嵌套骨架为`mlblack/examples/cases/cross_framework`：外层NestedTrainerProblem调用CaseRuntime.invoke，内层inner_training返回TrainerResult。它现在调学习率，不接此Spec；要做结构搜索仍须给内Case新增明确graph spec输入，不能声称换一个参数名即支持。仅想训练固定结构时，先使用上面的正式文本Case。

### 变体一：先把任务固定成一个结构

**目的：** 使用已闭合的固定模型Case，减少迁移面。

**改在哪里：** 在配置检查模块定义固定结构描述，不调用旧Problem：

```python
def fixed_task_shape():
    return {"vocab_size": 8, "max_length": 4, "hidden_dim": 8,
            "num_layers": 1, "num_heads": 2, "num_classes": 2}
```

**行为变化：** 从旧动态内fit回到已知固定结构的正式Case装配。**限制：** 这还不是结构优化的实现；必须将它标为替代路线，不能填造外层搜索运行结果。

源码：`mlblack/integrations/transformers_bridge.py`、`integrations/nsgablack_neural/transformer_spec_search.py`、`integrations/nsgablack_learning_case.py`、`examples/cases/cross_framework`与对应AGENTS。
