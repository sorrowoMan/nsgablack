"""
Project-level orchestration configuration.
"""
from typing import Dict, Any, List

# Define stages of execution. Each stage is a group of solvers that can be run in parallel.
STAGES: List[Dict[str, Any]] = [
    {
        "name": "stage_1",
        "cases": ["case_a"],
        "policy": "run_all_in_parallel",
    },
    {
        "name": "stage_2",
        "cases": ["case_b"],
        "policy": "run_all_in_parallel",
        "dependencies": {
            "case_b": {
                "artifacts": {
                    "input_data": "stage_1.case_a.output_data"
                }
            }
        }
    }
]

# Define groups of solvers. This can be used for more complex orchestration.
GROUPS: Dict[str, Any] = {
    "default": {
        "stages": ["stage_1", "stage_2"]
    }
}
