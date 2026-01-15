"""Component mixins for the multi-agent solver."""
from __future__ import annotations


from .advisor import AdvisorMixin
from .archive import ArchiveMixin
from .communication import CommunicationMixin
from .evolution import EvolutionMixin
from .region import RegionMixin
from .role_logic import RoleLogicMixin
from .scoring import ScoringMixin
from .utils import UtilsMixin

__all__ = [
    'AdvisorMixin',
    'ArchiveMixin',
    'CommunicationMixin',
    'EvolutionMixin',
    'RegionMixin',
    'RoleLogicMixin',
    'ScoringMixin',
    'UtilsMixin',
]

