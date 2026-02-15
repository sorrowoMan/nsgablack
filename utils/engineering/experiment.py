import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np
from .file_io import atomic_write_json


class ExperimentResult:
    """Structured experiment result container for NSGA runs."""

    def __init__(self, problem_name: str, config: Dict[str, Any]):
        self.problem_name = problem_name
        self.config = config
        self.timestamp = datetime.now().isoformat()
        self.pareto_front = None
        self.pareto_solutions = None
        self.metrics = {}
        self.history = []
        self.convergence_info = None

    def set_results(self, pareto_solutions, pareto_objectives, generation,
                   evaluation_count, elapsed_time, history=None, convergence_info=None):
        self.pareto_solutions = pareto_solutions
        self.pareto_front = pareto_objectives
        self.metrics = {
            'final_generation': generation,
            'evaluation_count': evaluation_count,
            'elapsed_time': elapsed_time,
            'pareto_size': len(pareto_objectives) if pareto_objectives is not None else 0
        }
        if history:
            self.history = history
        if convergence_info:
            self.convergence_info = convergence_info

    def save(self, output_dir: str, run_id: Optional[str] = None):
        """Save experiment to directory with pareto.csv, config.json, history.json."""
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        exp_dir = os.path.join(output_dir, f"{self.problem_name}_{run_id}")
        os.makedirs(exp_dir, exist_ok=True)

        # Save Pareto front
        if self.pareto_front is not None and len(self.pareto_front) > 0:
            np.savetxt(os.path.join(exp_dir, "pareto.csv"), self.pareto_front, delimiter=",")

        # Save config + metrics
        config_data = {
            'problem': self.problem_name,
            'timestamp': self.timestamp,
            'config': self.config,
            'metrics': self.metrics
        }
        atomic_write_json(os.path.join(exp_dir, "config.json"), config_data, ensure_ascii=False, indent=2)

        # Save history
        if self.history:
            def _to_serializable(obj):
                # Recursively convert numpy types to Python native types
                if isinstance(obj, np.ndarray):
                    return _to_serializable(obj.tolist())
                if isinstance(obj, (np.integer,)):
                    return int(obj)
                if isinstance(obj, (np.floating,)):
                    val = float(obj)
                    return None if np.isnan(val) else val
                if isinstance(obj, (list, tuple)):
                    return [_to_serializable(v) for v in obj]
                if isinstance(obj, dict):
                    return {k: _to_serializable(v) for k, v in obj.items()}
                if isinstance(obj, float):
                    return None if np.isnan(obj) else obj
                # fallback: try to leave as-is (json will handle str/int/bool/None)
                return obj

            safe_history = _to_serializable(self.history)
            atomic_write_json(
                os.path.join(exp_dir, "history.json"),
                {"history": safe_history},
                ensure_ascii=False,
                indent=2,
                encoding="utf-8",
            )

        return exp_dir


class ExperimentTracker:
    """Optional lightweight experiment tracking."""

    def __init__(self, base_dir: str = "./experiments"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def log_run(self, result: ExperimentResult, run_id: Optional[str] = None):
        """Log experiment result to disk."""
        return result.save(self.base_dir, run_id)
