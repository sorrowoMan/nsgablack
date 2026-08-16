"""
Project-level orchestration configuration.
"""
from typing import Dict, Any, List

# Define serial stages. Unsupported policies fail explicitly instead of being
# silently executed with different semantics.
STAGES: List[Dict[str, Any]] = [
    {
        "name": "stage_1",
        "cases": ["case_a"],
        "policy": "serial",
    },
    {
        "name": "stage_2",
        "cases": ["case_b"],
        "policy": "serial",
    }
]

# Define groups of solvers. This can be used for more complex orchestration.
GROUPS: Dict[str, Any] = {
    "default": {
        "stages": ["stage_1", "stage_2"]
    }
}
