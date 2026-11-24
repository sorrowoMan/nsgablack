# 符号函数空间：原语生成、动态更新与真正的模型消费者

FunctionPool保存当前候选表达式及其**训练数据上的物化值**；它不是优化运行的SolutionPool，也不含SolutionRef版本/事务。FunctionSpace补充特征名称和原语注册表描述，FunctionSpaceProvider是契约基类，不是独立求解器。以下一个完整应用把这些值实际交给固定符号表示；没有运行数据生成、表达式、搜索、模型或外部请求。

## mlblack.symbolic_pipeline.function_pool_pipeline · 生成表达式，再冻结为可搜索的参数模型

**什么时候用：** 用少量已知原语从训练数据生成候选表达式，按残差信号尝试扩展，然后明确选择一个结构、交给数值Adapter拟合参数。不是在候选求值中偷偷训练所有可能结构。

**先准备什么：** 复制完整 `mlblack/examples/cases/catalog_codec_demo/`，保存 [固定符号书的正式host](ML_SYMBOLIC_FIXED_APPLICATIONS_CN.md#symbolicfixedhost--完整正式构造与结果读取) 的builder/report入口。保留原Project/L0/default单Case，依赖当前三仓和NumPy。32训练/12验证、两特征；原语和排名只看训练数据。

**放在哪：** 完整替换Case config.py、pipeline/main.py、problem/__init__.py；共用host调用build_components/build_problem。原pipeline包继续有build_pipeline导出。

**接入步骤：** config.py：

```python
EXPAND = True
```

pipeline/main.py的第一部分，保存到同一个文件：

```python
import numpy as np
from mlblack.models import unary_expr, binary_expr
from mlblack.models.symbolic import parameterize_expression
from mlblack.pipeline import NumericDataView
from mlblack.pipeline.symbolic import (UnaryPrimitiveSpec, PairGrammarRule, PrimitiveRegistry,
    FunctionSpaceProvider, FunctionSpace, FunctionPool, CandidateTerm,
    FunctionPoolPipeline, FunctionPoolPipelineConfig,
    DynamicFunctionPoolPipeline, DynamicPoolConfig)
from mlblack.representations import SymbolicExpressionConfig, SymbolicExpressionRepresentation
from ..config import EXPAND

def square_expr(arg, params):
    return unary_expr("square", arg)

def square_values(x, params):
    return np.asarray(x, dtype=float)**2

def square_name(name, params):
    return "square(" + name + ")"

def product_expr(left, right, params):
    return binary_expr("mul", left, right)

def product_values(left, right, params):
    return np.asarray(left)*np.asarray(right)

def product_name(left, right, params):
    return "(" + left + "*" + right + ")"

def build_registry():
    return PrimitiveRegistry(unary_specs=(UnaryPrimitiveSpec(key="square",
        activation_family="poly", output_family="poly", complexity=2.,
        build_expr=square_expr, evaluate_values=square_values, build_name=square_name),),
        pair_rules=(PairGrammarRule(key="product", activation_family="interaction_basic",
            output_family="interaction", complexity=3., build_expr=product_expr,
            evaluate_values=product_values, build_name=product_name),))
```

表达式构造函数、数值函数和名称函数必须描述同一操作；框架不会证明二者等价。本例square和product均使用真实表达式节点和对应NumPy值。PrimitiveRegistry是真正传入初始与动态生成器的实例；family过滤针对activation_family，不按显示名称猜。

## symbolic.function_pool.wiring · 物化结果实际成为模型结构

在同一个pipeline/main.py末尾接上以下完整函数；不是第二个文件或运行器：

```python
def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 2)), rng.uniform(-1., 1., (12, 2))
    def target(a):
        return 2.*a[:, 0]**2 + a[:, 0]*a[:, 1]
    data = NumericDataView(X_train=X, y_train=target(X), X_valid=V, y_valid=target(V),
        feature_names=("x0", "x1"))
    registry = build_registry()
    provider = FunctionPoolPipeline(FunctionPoolPipelineConfig(
        include_unary=False, include_pairs=False, include_conditional=False, max_terms=8),
        registry=registry)
    if not isinstance(provider, FunctionSpaceProvider):
        raise TypeError("expected declared function-space provider")
    space = provider.build(data.X_train, y=data.y_train, feature_names=data.effective_feature_names)
    delta = None
    if EXPAND:
        updater = DynamicFunctionPoolPipeline(DynamicPoolConfig(
            residual_corr_threshold=0., expand_unary_families=("poly",),
            expand_pair_families=("interaction_basic",), dynamic_top_k_features=2,
            dynamic_pair_top_k=2, max_added_terms=8, max_active_terms=8), registry=registry)
        update = updater.update(data.X_train, base_pool=space.pool, y=data.y_train,
            residuals=data.y_train-float(data.y_train.mean()),
            budget_remaining_ratio=.5, feature_names=data.effective_feature_names)
        delta = update.as_dict()
        space = FunctionSpace(pool=update.pool, feature_names=space.feature_names,
            registry_summary=registry.describe(), metadata={"dynamic_update": delta})
    if not isinstance(space.pool, FunctionPool) or not space.pool.terms:
        raise ValueError("no usable expression terms")
    selected = space.pool.top_by_prior_corr(1).terms[0]
    if not isinstance(selected, CandidateTerm):
        raise TypeError("expected materialized symbolic term")
    prepared = {"space": space.describe(include_values=False),
                "selected": selected.describe(include_values=False), "update": delta}
    return NumericDataView(X_train=data.X_train, y_train=data.y_train,
        X_valid=data.X_valid, y_valid=data.y_valid, feature_names=data.feature_names,
        metadata={"function_preparation": prepared})

def build_components():
    data = build_pipeline()
    selected = data.metadata["function_preparation"]["selected"]
    expression = parameterize_expression(selected["expr"], prefix="selected",
                                        unary_input_affine=False)
    rep = SymbolicExpressionRepresentation(SymbolicExpressionConfig(input_dim=2,
        expression=expression, feature_names=data.effective_feature_names))
    return data, rep
```

初始pool只有两个seed特征；动态调用实际启用自定义square/product原语及其递归组合。这里残差来自“训练标签减训练均值”的固定基准，budget_remaining_ratio=.5也是应用明确给出的信号，**不是读取了正在运行的Solver反馈或实时授权预算**。没有真实残差就不能谎称已做在线反馈驱动搜索。

Dynamic更新会去重、按相关/冗余规则裁剪；added_terms可能为空，实际查看delta计数与reasons，不根据EXPAND推断一定变多。max_added_terms是生成阶段限制，max_active_terms才约束当前池；保留具体expr而不是仅存会随顺序变化的index。CandidateTerm.key是表达式等价键，不是运行候选token，不能当SolutionRef。

prior_corr由训练目标计算，只是候选特征的排序启发式，不是完整预测质量。选中term后包一层输出scale与bias，共2个参数，冻结结构再创建Solver。后续模型在验证X上重新解释expr，不能把CandidateTerm.values那32个训练值直接拿去充当12行验证预测。FunctionSpaceProvider本身只有契约，实际build由FunctionPoolPipeline实现。

problem/__init__.py完整内容：

```python
from dataclasses import replace
from mlblack.core.artifacts import SymbolicModelArtifact
from mlblack.problems import FixedSymbolicRegressionProblem

class GeneratedExpressionProblem(FixedSymbolicRegressionProblem):
    def evaluate(self, model, state, context):
        feedback = super().evaluate(model, state, context)
        selected = self.data.metadata["function_preparation"]["selected"]
        return replace(feedback, signals={**dict(feedback.signals), "selected_term": selected["name"]})

    def build_model_artifact(self, model, context):
        return SymbolicModelArtifact(name="generated_then_fitted", family="symbolic", head="point",
            model={"model": model.describe(),
                   "preparation": dict(self.data.metadata["function_preparation"])})

def build_problem(data):
    return GeneratedExpressionProblem(data, use_valid_objective=False, l2=0., complexity_weight=0.)
```

**怎样判断接对：** symbolic.json目标为[train.mse,0]，valid只观察，selected_term说明真正被拟合的结构。模型Artifact保存完整原语描述、选中表达式、动态delta与已评估参数；values不重复持久化成验证结果。单个term不一定能表达两项真实目标，即使相关最大也可有不可消除误差；8步不保证系数最优。本例不进行跨步骤替换活Codec布局。

**运行入口：** 依固定符号host执行Project check/build-check及run_symbolic_and_report.py；需要计算表达式的动作只发生在使用者真正运行时，本轮没有执行。Typed Artifact由正式Provider/finalization发布，未手写伪造引用。

### 变体一：只使用原始seed特征，不执行动态扩展

**目的：** 对比表达式来源而不是换求解器或目标。

**改在哪里：** config.py完整替换为：

```python
EXPAND = False
```

**行为变化：** 只从x0/x1的两个seed选一个，update为None；模型仍有输出scale/bias两参数。**限制：** 同维度不意味着结构或候选身份相同，不能复用原表达式状态/收据。FunctionPool不会自动追随主运行增加新项；真正在线结构更新须由明确所有者协调索引、冻结输入、状态和任务，不能在Decoder里偷偷换pool。

来源：mlblack/pipeline/symbolic/function_space.py、primitives.py、pool_pipeline.py、dynamic_pool.py、grammar.py、models/symbolic.py、representations/symbolic.py；完整正式Case入口见本记录的host来源。
