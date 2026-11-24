"""BO's observation dataset is distinct from active candidate membership."""
from dataclasses import dataclass, field
from typing import ClassVar

from .contracts import UnitSchema
from .features import FeatureUnit


@dataclass
class BayesianOptimizationUnit(FeatureUnit):
    unit_id: str
    owner_path: tuple = ()
    observations: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    model_revision: int = 0
    accepted_refs: list = field(default_factory=list)
    accepted_values: list = field(default_factory=list)
    last_acquisition: dict = field(default_factory=dict)
    schema: ClassVar = UnitSchema("bayesian_observations", required_fields=(
        "observations", "evidence", "model_revision", "accepted_refs", "accepted_values",
        "last_acquisition", "owner_path"), candidate_projection=False)

    def validate(self):
        identities = [tuple(row["identity"]) for row in self.observations]
        if len(identities) != len(set(identities)):
            raise ValueError("BO observation identities must be unique")
        if self.model_revision < 0 or len(self.accepted_refs) != len(self.accepted_values):
            raise ValueError("BO model revision/member references are invalid")
