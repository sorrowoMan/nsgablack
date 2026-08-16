from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MlblackEvalResult:
    rmse: float
    mae: float
    r2: float
    elapsed_sec: float
    run_dir: str


class MlblackFlowRunner:
    """Thin bridge: call mlblack standard flow from nsgablack outer loop."""

    def __init__(
        self,
        *,
        mlblack_root: str,
        csv_path: str,
        fold_col: str = "test_fold_1",
        output_root: str,
        target_col: str = "ci",
        random_seed: int = 7,
    ) -> None:
        self.mlblack_root = Path(mlblack_root).resolve()
        self.csv_path = str(Path(csv_path).resolve())
        self.fold_col = str(fold_col)
        self.output_root = Path(output_root).resolve()
        self.target_col = str(target_col)
        self.random_seed = int(random_seed)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, MlblackEvalResult] = {}
        self._imported = False

    def _ensure_mlblack_imports(self) -> None:
        if self._imported:
            return
        if not self.mlblack_root.exists():
            raise FileNotFoundError(f"mlblack_root not found: {self.mlblack_root}")
        if str(self.mlblack_root) not in sys.path:
            sys.path.insert(0, str(self.mlblack_root))
        self._imported = True

    def evaluate_xgboost(self, trainer_params: dict[str, Any]) -> MlblackEvalResult:
        self._ensure_mlblack_imports()

        # Late imports keep this bridge isolated from nsgablack runtime imports.
        from config import TrainerAssemblySpec  # type: ignore
        from core.orchestration.workflow import TrainFlowSpec, run_train_flow  # type: ignore
        from examples.work_ci_reader import WorkCiIntervalReader  # type: ignore

        key_payload = f"{self.fold_col}|{sorted((str(k), str(v)) for k, v in trainer_params.items())}"
        cache_key = hashlib.sha1(key_payload.encode("utf-8")).hexdigest()[:12]
        if cache_key in self._cache:
            return self._cache[cache_key]

        run_dir = self.output_root / f"inner_{self.fold_col}_{cache_key}"
        reader = WorkCiIntervalReader(
            csv_path=self.csv_path,
            target_col=self.target_col,
            test_fold_col=self.fold_col,
        )
        flow_spec = TrainFlowSpec(
            assembly=TrainerAssemblySpec(
                trainer_key="xgboost",
                pipeline_key="identity",
                trainer_params=dict(trainer_params),
            ),
            eval_splits=("test",),
            output_dir=str(run_dir),
            save_artifact=False,
            save_report=True,
            run_name=f"nested_{cache_key}",
        )
        t0 = time.perf_counter()
        result = run_train_flow(reader, spec=flow_spec)
        sec = float(time.perf_counter() - t0)
        test_metrics = dict(result.metrics.get("test", {}))
        out = MlblackEvalResult(
            rmse=float(test_metrics.get("rmse", float("inf"))),
            mae=float(test_metrics.get("mae", float("inf"))),
            r2=float(test_metrics.get("r2", float("-inf"))),
            elapsed_sec=sec,
            run_dir=str(run_dir),
        )
        self._cache[cache_key] = out
        return out
