"""Template for function-style biases using BiasModule."""
from __future__ import annotations

from typing import Dict, Optional
import numpy as np

from .bias import BiasModule


def penalty_template(x, constraints=None, context: Optional[Dict] = None) -> Dict[str, float]:
    """Return a penalty dict. Higher penalty = worse."""
    constraints = constraints or []
    violation = float(np.maximum(0.0, np.asarray(constraints)).sum()) if constraints else 0.0
    return {"penalty": violation, "constraint": violation}


def reward_template(x, constraints=None, context: Optional[Dict] = None) -> Dict[str, float]:
    """Return a reward dict. Higher reward = better."""
    return {"reward": float(np.mean(x))}


def build_bias_module() -> BiasModule:
    """Build a BiasModule with the template penalty and reward."""
    bias = BiasModule()
    bias.add_penalty(penalty_template, weight=1.0, name="constraint_penalty")
    bias.add_reward(reward_template, weight=0.05, name="mean_reward")
    return bias
