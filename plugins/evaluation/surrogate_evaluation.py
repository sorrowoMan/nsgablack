from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..base import Plugin
from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.extension_contracts import (
    ContractError,
    normalize_candidate,
    normalize_objectives,
    normalize_violation,
)
from ...utils.context.context_keys import (
    KEY_METRICS,
    KEY_METRICS_SURROGATE_STD,
)


@dataclass
class SurrogateEvaluationConfig:
    # 训练样本达到该数量后才启用 surrogate 筛选（此前全部真实评估）
    min_train_samples: int = 30

    # 每次 evaluate_population 至少做多少真实评估
    # 允许为 0：表示本轮不强制真实评估（仅在 surrogate 已可用时建议使用）
    min_true_evals: int = 6

    # 额外策略：选择预测最优的 top-k 做真实评估（抑制模型偏差）
    topk_exploit: int = 6

    # 额外策略：选择不确定性最高的 top-k 做真实评估（主动学习）
    topk_explore: int = 6

    # 每次调用后是否立即重训（更稳健但更慢）
    retrain_every_call: bool = True

    # 目标聚合方式（用于“预测最优 top-k”排序）
    objective_aggregation: str = "sum"  # "sum" or "first"

    random_seed: Optional[int] = 0


class SurrogateEvaluationPlugin(Plugin):
    is_algorithmic = True
    context_requires = ()
    context_provides = (KEY_METRICS_SURROGATE_STD,)
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Uses surrogate prediction with partial true evaluations; "
        "optionally writes surrogate uncertainty into context.metrics."
    )
    """使用 surrogate 接管 evaluate_population 的能力插件。

    设计原则：
    - 不污染 solver 核心：通过短路事件 evaluate_population 接入。
    - 仅减少真实评估次数，不改变表示/偏置/策略模块边界。
    - 训练数据来自真实评估点，预测仅用于筛选与排序。
    """

    def __init__(
        self,
        name: str = "surrogate_evaluation",
        *,
        config: Optional[SurrogateEvaluationConfig] = None,
        model_type: str = "rf",
        surrogate: Any = None,
        online_training: bool = True,
        parallel_evaluator: Any = None,
        parallel_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or SurrogateEvaluationConfig()
        self.model_type = str(model_type)
        # Optional: allow using a pre-trained surrogate model (capability-layer only).
        self._surrogate = surrogate
        self.online_training = bool(online_training)
        self.parallel_evaluator = parallel_evaluator
        self.parallel_kwargs = dict(parallel_kwargs or {})

        self._rng = np.random.default_rng(self.cfg.random_seed)

        self._X: list[np.ndarray] = []
        self._Y: list[np.ndarray] = []

        self.stats = {
            "true_evals": 0,
            "surrogate_calls": 0,
            "train_samples": 0,
        }

    def on_solver_init(self, solver):
        if self._surrogate is not None:
            return

        # 延迟 import，避免把 sklearn 强绑定到核心路径
        from ...utils.surrogate.vector_surrogate import VectorSurrogate

        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        self._surrogate = VectorSurrogate(num_objectives=n_obj, model_type=self.model_type)  # type: ignore[arg-type]

    # ---- short-circuit hook: BlankSolverBase.evaluate_population(...) ----
    def evaluate_population(self, solver, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self._surrogate is None:
            raise RuntimeError("SurrogateEvaluationPlugin not initialized (missing on_solver_init call)")

        pop = np.asarray(population)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)

        n = int(pop.shape[0])
        if n == 0:
            return np.zeros((0, int(getattr(solver, "num_objectives", 1) or 1))), np.zeros((0,), dtype=float)

        # 标准化候选解（形状 + 维度）
        xs = [normalize_candidate(pop[i], dimension=int(solver.dimension), name=f"population[{i}]") for i in range(n)]
        X = np.stack(xs, axis=0)

        # 先算约束（通常比真实目标评估便宜；即使 surrogate 也需要 violations）
        cons_list = []
        vio_list = []
        for i in range(n):
            cons, vio = evaluate_constraints_safe(solver.problem, X[i])
            cons_list.append(cons)
            vio_list.append(float(vio))
        violations = np.asarray(vio_list, dtype=float)

        # 数据不足时：全真实评估（同时累积训练数据）
        # 若使用“预训练代理 + 关闭在线训练”，可直接进入 surrogate 模式
        if self.online_training and len(self._X) < int(self.cfg.min_train_samples):
            objectives = self._true_evaluate(solver, X, cons_list, violations)
            self._append_training(X, objectives)
            self._maybe_retrain()
            return objectives, violations

        # 1) surrogate 预测全体
        self.stats["surrogate_calls"] += 1
        pred = np.asarray(self._surrogate.predict(X), dtype=float)
        if pred.ndim != 2:
            raise ContractError("surrogate.predict must return 2D array with shape (N, M)")

        # 2) 选择要做真实评估的子集（exploitation + exploration + min_true_evals）
        selected = self._select_indices_for_true_eval(X, pred)
        if not selected and int(self.cfg.min_true_evals) > 0:
            selected = [int(self._rng.integers(0, n))]

        # 3) 对 selected 做真实评估并回填结果
        if selected:
            true_X = X[selected]
            true_cons = [cons_list[i] for i in selected]
            true_vio = violations[selected]
            true_obj = self._true_evaluate(solver, true_X, true_cons, true_vio)
            pred[selected] = true_obj

            # 4) 用真实评估结果更新训练集，并按配置重训
            if self.online_training:
                self._append_training(true_X, true_obj)
                self._maybe_retrain()

        # 4.5) compute per-candidate uncertainty for bias consumption (best-effort)
        unc_score = None
        try:
            unc = np.asarray(self._surrogate.uncertainty(X), dtype=float)
            if unc.ndim == 2:
                unc_score = np.mean(unc, axis=1)
            else:
                unc_score = np.asarray(unc, dtype=float).reshape(-1)
        except Exception:
            unc_score = None

        # 5) 应用偏置（对预测值/真值统一处理，保持与 Adapter/update 语义一致）
        out_obj = np.zeros_like(pred, dtype=float)
        for i in range(n):
            obj_i = normalize_objectives(pred[i], num_objectives=int(solver.num_objectives), name="surrogate.objectives")
            ctx = solver.build_context(individual_id=i, constraints=cons_list[i], violation=float(violations[i]))
            if unc_score is not None and i < len(unc_score):
                metrics = ctx.get(KEY_METRICS)
                if not isinstance(metrics, dict):
                    metrics = {}
                    ctx[KEY_METRICS] = metrics
                metrics[KEY_METRICS_SURROGATE_STD.split(".", 1)[1]] = float(unc_score[i])
            if getattr(solver, "enable_bias", False) and getattr(solver, "bias_module", None) is not None:
                obj_i = solver._apply_bias(obj_i, X[i], i, ctx)
            out_obj[i] = obj_i

        return out_obj, violations

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _append_training(self, X: np.ndarray, objectives: np.ndarray) -> None:
        X_arr = np.asarray(X, dtype=float)
        Y_arr = np.asarray(objectives, dtype=float)
        if Y_arr.ndim == 1:
            Y_arr = Y_arr.reshape(-1, 1)
        for i in range(X_arr.shape[0]):
            self._X.append(X_arr[i].copy())
            self._Y.append(Y_arr[i].copy())
        self.stats["train_samples"] = len(self._X)

    def _maybe_retrain(self) -> None:
        if not self.cfg.retrain_every_call:
            return
        if self._surrogate is None:
            return
        X = np.asarray(self._X, dtype=float)
        Y = np.asarray(self._Y, dtype=float)
        if X.size == 0:
            return
        self._surrogate.fit(X, Y)

    def _select_indices_for_true_eval(self, X: np.ndarray, pred: np.ndarray) -> list[int]:
        n = int(X.shape[0])
        scores = self._aggregate_objectives(pred)
        # exploitation: 预测最优样本
        exploit_k = min(int(self.cfg.topk_exploit), n)
        exploit = list(np.argsort(scores)[:exploit_k])

        # exploration: 不确定性最高样本
        unc = np.asarray(self._surrogate.uncertainty(X), dtype=float)
        if unc.ndim == 2:
            unc_score = np.mean(unc, axis=1)
        else:
            unc_score = np.asarray(unc, dtype=float).reshape(-1)
        explore_k = min(int(self.cfg.topk_explore), n)
        explore = list(np.argsort(unc_score)[-explore_k:])

        selected = set(int(i) for i in exploit + explore)

        # 保底数量（允许为 0）
        min_true = min(max(0, int(self.cfg.min_true_evals)), n)
        if min_true > 0:
            while len(selected) < min_true:
                selected.add(int(self._rng.integers(0, n)))

        return sorted(selected)

    def _aggregate_objectives(self, objectives: np.ndarray) -> np.ndarray:
        arr = np.asarray(objectives, dtype=float)
        if arr.ndim == 1:
            return arr
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            return arr[:, 0]
        return np.sum(arr, axis=1)

    def _true_evaluate(
        self,
        solver,
        X: np.ndarray,
        cons_list: list[np.ndarray],
        violations: np.ndarray,
    ) -> np.ndarray:
        # 可选并行：由能力层主动调用，并保持 Bias/constraints 对齐
        if self.parallel_evaluator is not None and getattr(X, "shape", (0,))[0] > 0:
            try:
                # NOTE: bias is disabled here. _true_evaluate returns raw objectives;
                # bias is applied once in evaluate_population Step 5.
                objs, vios = self.parallel_evaluator.evaluate_population(
                    np.asarray(X, dtype=float),
                    problem=getattr(solver, "problem", None),
                    enable_bias=False,
                    bias_module=None,
                    num_objectives=int(getattr(solver, "num_objectives", 1) or 1),
                    extra_context={"generation": int(getattr(solver, "generation", 0) or 0)},
                    **self.parallel_kwargs,
                )
                # 并行评估返回的 violation 更权威（可能来自 context_builder）
                violations[:] = np.asarray(vios, dtype=float).reshape(-1)
                self.stats["true_evals"] += int(np.asarray(X).shape[0])
                solver.evaluation_count += int(np.asarray(X).shape[0])
                return np.asarray(objs, dtype=float)
            except Exception:
                # 并行失败时回退串行
                pass

        n = int(np.asarray(X).shape[0])
        out = np.zeros((n, int(getattr(solver, "num_objectives", 1) or 1)), dtype=float)
        for i in range(n):
            val = solver.problem.evaluate(X[i])
            obj = normalize_objectives(val, num_objectives=int(solver.num_objectives), name="problem.evaluate")
            # NOTE: bias is NOT applied here. _true_evaluate returns raw objective
            # values so that (1) training data stays unbiased (N-02) and (2) bias
            # is applied exactly once in evaluate_population Step 5 (N-01).
            out[i] = obj

        self.stats["true_evals"] += n
        solver.evaluation_count += n
        return out
