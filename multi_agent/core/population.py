from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .role import AgentRole


@dataclass
class AgentPopulation:
    """Agent population container."""

    role: AgentRole
    population: List[np.ndarray]
    objectives: List[List[float]]
    constraints: List[List[float]]
    fitness: List[float]
    bias_profile: Dict
    generation: int = 0
    best_individual: Optional[np.ndarray] = None
    best_objectives: Optional[List[float]] = None
    best_constraints: Optional[List[float]] = None
    representation_pipeline: Optional['RepresentationPipeline'] = None
    score: float = 0.0
    last_best_objectives: Optional[List[float]] = None
    feasible_rate: float = 0.0
    avg_violation: float = 0.0

