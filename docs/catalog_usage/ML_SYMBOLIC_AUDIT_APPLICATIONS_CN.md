# 符号审计工具：实际读取已拟合模型，保持评估与决策分开

本例复制完整 `mlblack/examples/cases/catalog_codec_demo/`。下文是一个正式Case，ModelRepresentation/Problem负责训练语义，审计工具在模型Artifact准备时读取冻结的已拟合参数；它们不自动接管Adapter选择。依赖三仓/NumPy，SQLite只在显式变体启用。本轮没有运行模型、数据、数据库、网络或算法。

## mlblack.nsgablack_symbolic.symbolic_candidate_scorer · 把评分、保护与报告接到具体模型

**什么时候用：** 要解释同一表达式的结构、训练/验证差异、折叠或区域诊断，保存可对照的报告；不能只实例化一个Guard就宣称硬准入已开启。

**先准备什么：** 完整Project副本，保留原default/L0/Case标记和规范CLI。训练32、验证12，一输入，固定结构b+w*x；本例用Gaussian拟合2参数。审计会额外做表达式/预测统计，有实际CPU成本，不等同搜索Problem调用次数。

**放在哪：** 完整替换Case config.py、pipeline/main.py、problem/__init__.py、build_solver.py；新增plugins/path_observation.py。Project根的结果读取入口使用 [固定符号host](ML_SYMBOLIC_FIXED_APPLICATIONS_CN.md#symbolicfixedhost--完整正式构造与结果读取) 中的run_symbolic_and_report.py；不要复制其builder覆盖本例builder。

**接入步骤：** config.py：

```python
FOLDS = 3
USE_MEMORY = False
```

pipeline/main.py：

```python
import numpy as np
from mlblack.models import binary_expr, feature_expr, param_expr
from mlblack.pipeline import NumericDataView
from mlblack.representations import SymbolicExpressionConfig, SymbolicExpressionRepresentation

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 1)), rng.uniform(-1., 1., (12, 1))
    def target(a):
        return 1.+2.*a[:, 0] + .05*np.sin(4.*a[:, 0])
    return NumericDataView(X_train=X, y_train=target(X), X_valid=V, y_valid=target(V),
                           feature_names=("x",))

def build_components():
    expression = binary_expr("add", param_expr("b", init=0.),
        binary_expr("mul", param_expr("w", init=1.), feature_expr(0)))
    return build_pipeline(), SymbolicExpressionRepresentation(SymbolicExpressionConfig(
        input_dim=1, expression=expression, feature_names=("x",)))
```

problem/__init__.py的imports和辅助函数如下，下一节继续同一文件：

```python
from types import SimpleNamespace
import numpy as np
from mlblack.core.artifacts import SymbolicModelArtifact
from mlblack.models.symbolic import expression_complexity
from mlblack.pipeline import NumericDataView
from mlblack.pipeline.symbolic import CandidateTerm, FunctionPool
from mlblack.problems import FixedSymbolicRegressionProblem
from mlblack.integrations.nsgablack_symbolic.artifacts import OrthogonalBasisSetArtifact, SymbolicTaskArtifact
from mlblack.integrations.nsgablack_symbolic.search_space import FunctionPoolIndexSearchSpace
from mlblack.integrations.nsgablack_symbolic.graph_cache import ExpressionGraphCache
from mlblack.integrations.nsgablack_symbolic.overfit_guard import SymbolicOverfitGuard
from mlblack.integrations.nsgablack_symbolic.structure_guard import SymbolicStructureGuard
from mlblack.integrations.nsgablack_symbolic.search_policy import SymbolicCandidateScorer
from mlblack.integrations.nsgablack_symbolic.replay import SymbolicReplayRecordBuilder
from mlblack.integrations.nsgablack_symbolic.expression_audit import SymbolicExpressionAuditProducer
from mlblack.integrations.nsgablack_symbolic.basis_consensus import SymbolicBasisConsensusAnalyzer
from mlblack.integrations.nsgablack_symbolic.evaluation import (
    SymbolicFoldEvaluator, SymbolicFoldEvaluationConfig,
    SymbolicBranchEvaluator, SymbolicBranchEvaluationConfig, SymbolicBranchSpec)
from ..config import FOLDS

def measurements(model, data):
    metrics = {}
    for prefix, X, y in (("train", data.X_train, data.y_train), ("valid", data.X_valid, data.y_valid)):
        mse = float(np.mean((model.predict(X)-y)**2))
        metrics[prefix+".mse"] = mse
        metrics[prefix+".rmse"] = float(np.sqrt(mse))
    return metrics
```

## symbolic.audit.problem · Artifact准备时真实调用的工具链

在同一problem/__init__.py末尾接上：

```python
class AuditedProblem(FixedSymbolicRegressionProblem):
    def build_model_artifact(self, model, context):
        metrics = measurements(model, self.data)
        cache = ExpressionGraphCache(backend="memory", max_value_entries=8, max_derivative_entries=8)
        try:
            prediction = cache.evaluate_expression(model.expression, self.data.X_train,
                param_values=model.param_values)
            cache.evaluate_expression(model.expression, self.data.X_train, param_values=model.param_values)
            cache.differentiate_wrt_feature(model.expression, feature_index=0)
            cache_report = cache.snapshot()
        finally:
            cache.close()
        term = CandidateTerm(name="fitted_expression", expr=dict(model.expression), values=prediction,
            complexity=expression_complexity(model.expression), family="fitted", activation_family="fitted",
            features=(0,))
        space = FunctionPoolIndexSearchSpace(FunctionPool((term,)), dimension=1, allow_duplicates=False)
        selected = space.decode_terms((0.,))
        overfit, structure = SymbolicOverfitGuard(), SymbolicStructureGuard()
        scorer = SymbolicCandidateScorer(overfit_guard=overfit, structure_guard=structure)
        score = scorer.score(objectives=(metrics["train.mse"], 0.), selected_terms=selected,
            metrics=metrics, expression=model.expression, record_memory=False)
        params = tuple(float(v) for v in model.parameter_vector())
        task = SymbolicTaskArtifact(name="fitted_point", expression=dict(model.expression),
            fitted_state=params, metrics=metrics, objectives=(metrics["train.mse"], 0.), constraints=(),
            selected_indices=(0,), selected_terms=(term.describe(include_values=False),),
            task_kind="regression", head_kind="point")
        basis = OrthogonalBasisSetArtifact(name="one_fitted_atom", input_dim=1, feature_names=("x",),
            basis_genome=({"name": "atom", "expr": dict(model.expression)},), fitted_state=params,
            selected_indices=(0,), selected_terms=(term.describe(include_values=False),))
        heldout = NumericDataView(X_train=self.data.X_valid, y_train=self.data.y_valid, feature_names=("x",))
        folds = SymbolicFoldEvaluator(SymbolicFoldEvaluationConfig(n_splits=FOLDS, shuffle=False))
        fold_report = folds.evaluate_task_artifact(task, heldout).as_dict()
        branch_report = SymbolicBranchEvaluator(SymbolicBranchEvaluationConfig(
            branches=(SymbolicBranchSpec(name="left", kind="threshold", feature=0, op="<", threshold=0.),),
            min_branch_size=3, enable_branch_refit=False)).evaluate_task_artifact(task, heldout).as_dict()
        consensus = SymbolicBasisConsensusAnalyzer().analyze((basis,), X=self.data.X_train).as_dict()
        audit = SymbolicExpressionAuditProducer().analyze({"target": model.expression},
            selected_terms=task.selected_terms, feature_names=("x",), X=self.data.X_train).as_dict()
        record = SimpleNamespace(outer_candidate=(), selected_indices=(0,), selected_terms=task.selected_terms,
            fitted_state=params, objectives=task.objectives, constraints=(), metrics=metrics,
            signals={"stage": "post_fit_diagnostic"}, report={"candidate_score": score.as_dict()})
        replay = SymbolicReplayRecordBuilder().build(record, stage="post_fit_diagnostic",
            problem_name=self.name, extra_inputs={"expression": dict(model.expression)}).as_dict()
        return SymbolicModelArtifact(name="audited_symbolic", family="symbolic", head="point",
            model={"model": model.describe(), "task": task.describe(), "basis": basis.describe(),
                "reports": {"cache": cache_report, "candidate_score": score.as_dict(),
                    "fold": fold_report, "branch": branch_report, "consensus": consensus,
                    "expression_audit": audit, "replay": replay, "index_space": space.describe()}})

def build_problem(data):
    return AuditedProblem(data, use_valid_objective=False, complexity_weight=0., l2=0.)
```

这里FunctionPoolIndexSearchSpace只解释一个诊断term的index，不是额外执行外层结构算法；allow_duplicates=False只有当pool有足够项时才可能真正补齐不同项，不能当任意维度唯一性证明。其index不是SolutionRef。

缓存是本次Artifact分析的短寿命memory对象，不进入共享context或checkpoint。自动batch token当前基于数组身份/形状，不是内容摘要；调用期间不原位改X，不拿相同batch_key复用不同数据，也不改eps等求值设定。返回缓存数组按只读使用，命中率只说明复用，不证明表达式或导数数学正确。

CandidateScorer实际消费两个Guard，产生独立诊断分数；本Case的Adapter仍按原始训练MSE选择，Guard报告不自动变成硬约束或否决。overfit缺少metric时会报告missing而非凭空判断；structure的极点/冗余是数值启发式，不是函数域证明。诊断约束为空，不能据本例推断其它约束权重配置没有重复罚值等风险。

FoldEvaluator对**同一已拟合模型**做12条留出数据的分块评估，不重新拟合，不能称k折训练交叉验证。BranchEvaluator明确禁用branch_refit；已有源码启用该开关会另起直接内层训练，不属于本例受验收范围。单个basis的Consensus频率平凡，不是多独立运行稳定性证据。Audit的简化/等价/真值恢复是报告，不是数学证明或恢复权威。ReplayRecord是输入摘要，缺少完整运行状态/RNG/数据闭包，不能代替Solver checkpoint。

## symbolic.audit.wiring · 发布后记忆与完整builder

plugins/path_observation.py完整内容：

```python
from pathlib import Path
import numpy as np
from nsgablack.plugins.base import Plugin
from mlblack.integrations.nsgablack_symbolic.graph_cache import ExpressionGraphCache
from mlblack.integrations.nsgablack_symbolic.path_memory import SymbolicPathMemory

class PublishedPathObservation(Plugin):
    def __init__(self, enabled, path):
        super().__init__(name="published_path_observation")
        self.enabled, self.path = bool(enabled), Path(path)

    def on_solver_finalized(self, result):
        if not self.enabled:
            return
        model, feedback = self.solver.best_model, self.solver.best_feedback
        key = ExpressionGraphCache.expression_key(model.expression)
        score = float(np.sum(feedback.objectives))
        memory = SymbolicPathMemory(db_path=str(self.path), namespace="published_point_runs")
        try:
            memory.record_expr_outcome(key, selected_score=score, delta_score=-score, success=score < .1)
        finally:
            memory.close()
```

build_solver.py完整内容：

```python
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from .pipeline.main import build_components
from .problem import build_problem
from .plugins.path_observation import PublishedPathObservation
from .config import USE_MEMORY

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit components")
    data, rep = build_components()
    solver = build_learning_solver(problem=build_problem(data), representation=rep,
        adapter=build_optimization_adapter("search.random_gaussian", population_size=8,
            mutation_scale=.2, objective_aggregation="sum"),
        resource_context=resource_context, compute_backend="numpy", run_name="symbolic_audit")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(8)
    solver.add_plugin(PublishedPathObservation(USE_MEMORY,
        Path(__file__).resolve().parent / "results" / "published_paths.sqlite3"))
    return solver
```

PathMemory只在最终权威结果已发布后记录“这次完成运行的最终表达式”，不是每个提案。它不影响本Case的搜索评分，不是步骤事务参与者；success阈值.1是本应用给定的观察含义。写失败不能撤销已经发布的结果；重复送达该通知会重复计数，当前接口没有按run_id去重，不能盲目自动重试。模型表达式等价键也不包含参数数值或完整训练任务身份，实际跨任务复用须隔离namespace并自行定义可比较尺度。

**怎样判断接对：** symbolic.json保留[train.mse,0]与正式model_ref；模型JSON的reports明确包含score_parts/guard理由、cache统计、留出fold与branch条数、单basis共识、表达式审计和replay摘要。数值诊断在Artifact准备时由同一冻结模型重新计算，属于派生观察，不替代原Evaluation Event；没有宣称它们是又一次预算内搜索评估。默认没有创建数据库。

**运行入口：** 按固定符号host的Project检查与run_symbolic_and_report.py命令，读取新run_id/Case终态；本轮未运行。Artifact模型蓝图由正式finalization/ModelRef交付，SQLite路径记录不是另一个权威结果源。

### 变体一：启用发布后的路径观察

**目的：** 将完成运行的表达式观察保存在本Case结果目录，不把失败提案记成成功。

**改在哪里：** config.py完整替换为：

```python
FOLDS = 3
USE_MEMORY = True
```

**行为变化：** 成功发布后才打开本地SQLite、登记一次观察并关闭；之后可用SymbolicPathMemory.prior_summary读相同namespace。**限制：** 不是恢复步骤或免费观察，也没有自动把历史先验接回CandidateScorer；要参与搜索须显式设计评分/事务范围。本文没有连接SQLite或验证持久化。

来源：mlblack/integrations/nsgablack_symbolic的search_space、graph_cache、structure_guard、overfit_guard、search_policy、artifacts、evaluation、basis_consensus、expression_audit、replay、path_memory；其余模型与发布使用正式学习Case。

## symbolic.audit.runner · 本例唯一的结果读取入口

Project根 `run_symbolic_and_report.py`完整内容，避免另复制包含不同builder的host：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(c for c in run.case_results if c.request.case_name == "linear_point")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None or value.best_model_ref is None:
        raise ValueError("expected evaluated feedback and symbolic Artifact")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": value.best_model_ref.as_dict()}
    path = root / "results" / "symbolic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

在副本根先 `python run_project.py --check --build-check`，再 `python run_symbolic_and_report.py`。这段只委托正式Project，保留本例builder中的PathMemory观察器；本轮没有执行。
