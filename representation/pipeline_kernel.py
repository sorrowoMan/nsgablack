"""nsgablack representation adapter for the shared blackbase slot kernel.

The executable orchestration contract lives in :mod:`blackbase.kernel`.
This module adds only the ``RepresentationPipeline`` assembly expected by the
optimization layer and keeps the historical nsgablack import path working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Optional

from blackbase.kernel import (
    OrchestrationPolicy,
    PipelineSlotSpec,
    PipelineSpec,
    build_pipeline_kernel as build_shared_pipeline_kernel,
)

from .base import RepresentationPipeline


_PIPELINE_SLOT_NAMES = {"init", "initializer", "mutate", "repair", "encode", "decode"}


@dataclass
class PipelineKernelBuild:
    representation_pipeline: RepresentationPipeline | None = None
    slot_runners: Mapping[
        str,
        Callable[[Any, Optional[MutableMapping[str, Any]]], Any],
    ] = field(default_factory=dict)
    slot_policies: Mapping[str, OrchestrationPolicy] = field(default_factory=dict)
    operator_registry: Mapping[str, Any] = field(default_factory=dict)

    def run_slot(
        self,
        slot: str,
        value: Any,
        context: Optional[MutableMapping[str, Any]] = None,
    ) -> Any:
        key = str(slot or "").strip().lower().replace("-", "_").replace(" ", "_")
        runner = self.slot_runners.get(key)
        if runner is None:
            return value
        return runner(value, context)

    def as_dict(self) -> dict[str, Any]:
        return {
            "slots": sorted(self.slot_runners.keys()),
            "slot_policies": {key: policy.mode for key, policy in self.slot_policies.items()},
            "has_representation_pipeline": self.representation_pipeline is not None,
        }


def build_pipeline_kernel(
    spec: PipelineSpec | Mapping[str, Any] | None,
    *,
    operator_registry: Mapping[str, Any],
    strict: bool = True,
    executor: Any = None,
    pool_scheduler: Any = None,
) -> PipelineKernelBuild:
    """Build through blackbase and adapt standard slots to RepresentationPipeline."""
    shared = build_shared_pipeline_kernel(
        spec,
        operator_registry=operator_registry,
        strict=bool(strict),
        executor=executor,
        pool_scheduler=pool_scheduler,
    )
    pipeline_kwargs: dict[str, Any] = {}
    for slot_name, runner in shared.slot_runners.items():
        if slot_name in _PIPELINE_SLOT_NAMES:
            _set_pipeline_operator(pipeline_kwargs, slot_name, runner)

    return PipelineKernelBuild(
        representation_pipeline=RepresentationPipeline(**pipeline_kwargs),
        slot_runners=shared.slot_runners,
        slot_policies=shared.slot_policies,
        operator_registry=shared.operator_registry,
    )


def _set_pipeline_operator(
    target: dict[str, Any],
    slot_name: str,
    runner: Callable[[Any, Optional[dict]], Any],
) -> None:
    if slot_name in {"init", "initializer"}:
        target["initializer"] = _InitializerShim(runner)
        return
    if slot_name == "mutate":
        target["mutator"] = _MutatorShim(runner)
        return
    if slot_name == "repair":
        target["repair"] = _RepairShim(runner)
        return
    if slot_name == "encode":
        encoder = target.get("encoder")
        if isinstance(encoder, _EncoderShim):
            encoder.set_encode(runner)
        else:
            target["encoder"] = _EncoderShim(encode_fn=runner)
        return
    if slot_name == "decode":
        encoder = target.get("encoder")
        if isinstance(encoder, _EncoderShim):
            encoder.set_decode(runner)
        else:
            target["encoder"] = _EncoderShim(decode_fn=runner)


class _InitializerShim:
    def __init__(self, fn: Callable[[Any, Optional[dict]], Any]) -> None:
        self._fn = fn

    def initialize(self, problem: Any, context: Optional[dict] = None) -> Any:
        return self._fn(problem, context)


class _MutatorShim:
    def __init__(self, fn: Callable[[Any, Optional[dict]], Any]) -> None:
        self._fn = fn

    def mutate(self, value: Any, context: Optional[dict] = None) -> Any:
        return self._fn(value, context)


class _RepairShim:
    def __init__(self, fn: Callable[[Any, Optional[dict]], Any]) -> None:
        self._fn = fn

    def repair(self, value: Any, context: Optional[dict] = None) -> Any:
        return self._fn(value, context)


class _EncoderShim:
    def __init__(
        self,
        *,
        encode_fn: Callable[[Any, Optional[dict]], Any] | None = None,
        decode_fn: Callable[[Any, Optional[dict]], Any] | None = None,
    ) -> None:
        self._encode = encode_fn
        self._decode = decode_fn

    def set_encode(self, fn: Callable[[Any, Optional[dict]], Any]) -> None:
        self._encode = fn

    def set_decode(self, fn: Callable[[Any, Optional[dict]], Any]) -> None:
        self._decode = fn

    def encode(self, value: Any, context: Optional[dict] = None) -> Any:
        return value if self._encode is None else self._encode(value, context)

    def decode(self, value: Any, context: Optional[dict] = None) -> Any:
        return value if self._decode is None else self._decode(value, context)


__all__ = [
    "OrchestrationPolicy",
    "PipelineKernelBuild",
    "PipelineSlotSpec",
    "PipelineSpec",
    "build_pipeline_kernel",
]
