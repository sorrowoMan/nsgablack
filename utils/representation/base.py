"""
Representation pipeline for encoding, repair, initialization, and mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol


class EncodingPlugin(Protocol):
    def encode(self, x: Any, context: Optional[dict] = None) -> Any:
        ...

    def decode(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


class RepairPlugin(Protocol):
    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


class InitPlugin(Protocol):
    def initialize(self, problem: Any, context: Optional[dict] = None) -> Any:
        ...


class MutationPlugin(Protocol):
    def mutate(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


@dataclass
class RepresentationPipeline:
    encoder: Optional[EncodingPlugin] = None
    repair: Optional[RepairPlugin] = None
    initializer: Optional[InitPlugin] = None
    mutator: Optional[MutationPlugin] = None

    def init(self, problem: Any, context: Optional[dict] = None) -> Any:
        if self.initializer is None:
            raise ValueError("initializer is required for init()")
        x = self.initializer.initialize(problem, context)
        if self.repair is not None:
            x = self.repair.repair(x, context)
        return x

    def mutate(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.mutator is None:
            raise ValueError("mutator is required for mutate()")
        x = self.mutator.mutate(x, context)
        if self.repair is not None:
            x = self.repair.repair(x, context)
        return x

    def decode(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.encoder is None:
            return x
        return self.encoder.decode(x, context)

    def encode(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.encoder is None:
            return x
        return self.encoder.encode(x, context)
