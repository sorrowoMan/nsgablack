# -*- coding: utf-8 -*-
"""Project L0 runtime profiles.

Runtime config is the project-facing L0 entrypoint. It describes execution
profiles, resources, worker pools, queues, stores, artifact backends and data
transport without leaking those choices into problem/pipeline/adapter code.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, Mapping, Sequence

from nsgablack.core import GpuBackend, ProcessPoolBackend, ThreadPoolBackend
from blackbase.resources import ResourceRequirement


@dataclass(frozen=True)
class RuntimeBackendSpec:
    key: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeProfile:
    key: str
    summary: str = ""
    executor_backend: str = "local"
    resource_backend: str = "local"
    backend_keys: tuple[str, ...] = ()
    default_backend: str | None = None
    task_requirement: ResourceRequirement = field(default_factory=ResourceRequirement)
    queue_backend: str = "memory"
    result_backend: str = "memory"
    state_backend: str = "memory"
    worker_registry_backend: str = "memory"
    artifact_backend: str = "filesystem"
    data_transport_backend: str = "inline"
    lease_store: str = "memory"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": str(self.key),
            "summary": str(self.summary),
            "executor_backend": str(self.executor_backend),
            "resource_backend": str(self.resource_backend),
            "backend_keys": [str(x) for x in self.backend_keys],
            "default_backend": self.default_backend,
            "task_requirement": self.task_requirement.as_dict(),
            "queue_backend": str(self.queue_backend),
            "result_backend": str(self.result_backend),
            "state_backend": str(self.state_backend),
            "worker_registry_backend": str(self.worker_registry_backend),
            "artifact_backend": str(self.artifact_backend),
            "data_transport_backend": str(self.data_transport_backend),
            "lease_store": str(self.lease_store),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeRegistry:
    profiles: tuple[RuntimeProfile, ...] = ()
    backends: tuple[RuntimeBackendSpec, ...] = ()


def get_runtime_registry() -> RuntimeRegistry:
    return RuntimeRegistry(
        profiles=(
            RuntimeProfile(
                key="local_cpu",
                summary="Default local CPU runtime; no explicit parallel backend.",
                task_requirement=ResourceRequirement(
                    threads=1,
                    gpus=0,
                    capabilities=("local_cpu",),
                    metadata={"role": "default_project_runtime"},
                ),
            ),
            RuntimeProfile(
                key="threaded_cpu",
                summary="Local thread pool for parallel evaluation.",
                executor_backend="thread",
                backend_keys=("thread",),
                default_backend="thread",
                task_requirement=ResourceRequirement(
                    threads=1,
                    gpus=0,
                    capabilities=("local_cpu", "parallel_eval"),
                    metadata={"pool": "thread"},
                ),
            ),
            RuntimeProfile(
                key="process_cpu",
                summary="Local process pool; use SQLite lease store if GPU is involved.",
                executor_backend="process",
                backend_keys=("process",),
                default_backend="process",
                lease_store="sqlite",
                task_requirement=ResourceRequirement(
                    threads=1,
                    gpus=0,
                    capabilities=("local_cpu", "process_eval"),
                    metadata={"pool": "process"},
                ),
            ),
            RuntimeProfile(
                key="local_gpu",
                summary="Local GPU-aware execution profile with explicit device token.",
                executor_backend="gpu",
                backend_keys=("gpu",),
                default_backend="gpu",
                lease_store="sqlite",
                data_transport_backend="artifact_ref",
                task_requirement=ResourceRequirement(
                    threads=2,
                    gpus=1,
                    device_tokens=("cuda:0",),
                    capabilities=("cuda", "gpu_eval"),
                    metadata={"gpu_sharing": "exclusive"},
                ),
            ),
        ),
        backends=(
            RuntimeBackendSpec(key="thread", kind="executor", params={"scope": "evaluation", "workers": None}),
            RuntimeBackendSpec(key="process", kind="executor", params={"scope": "evaluation", "workers": None}),
            RuntimeBackendSpec(
                key="gpu",
                kind="executor",
                params={"scope": "evaluation", "gpu_backend": "auto", "gpu_device": "cuda:0"},
            ),
        ),
    )


def resolve_runtime_profile(registry: RuntimeRegistry, key: str = "local_cpu") -> RuntimeProfile:
    lookup = str(key or "local_cpu").strip().lower()
    for profile in tuple(registry.profiles or ()):
        if str(profile.key).strip().lower() == lookup:
            return profile
    raise ValueError(f"Runtime profile not registered: {key}")


def _find_backend_spec(registry: RuntimeRegistry, key: str) -> RuntimeBackendSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.backends or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Runtime backend not registered: {key}")


def _set_default_backend(solver, scope: str, backend: str) -> None:
    setter = getattr(solver, "set_acceleration_default_backend", None)
    if callable(setter):
        setter(scope=scope, backend=backend)


def _register_executor_backend(solver, spec: RuntimeBackendSpec) -> tuple[str, str] | None:
    key = str(spec.key).strip().lower()
    params = dict(spec.params or {})
    scope = str(params.pop("scope", "evaluation"))
    register = getattr(solver, "register_acceleration_backend", None)
    if not callable(register):
        return None
    if key == "thread":
        register(
            scope=scope,
            backend="thread",
            factory=lambda: ThreadPoolBackend(max_workers=params.get("workers")),
        )
        return scope, "thread"
    if key == "process":
        register(
            scope=scope,
            backend="process",
            factory=lambda: ProcessPoolBackend(max_workers=params.get("workers")),
        )
        return scope, "process"
    if key == "gpu":
        register(
            scope=scope,
            backend="gpu",
            factory=lambda: GpuBackend(
                preferred_backend=str(params.get("gpu_backend", "auto")),
                device=str(params.get("gpu_device", "cuda:0")),
            ),
        )
        return scope, "gpu"
    raise ValueError(f"Unknown runtime executor backend key: {spec.key}")


def apply_runtime_profile(
    solver,
    registry: RuntimeRegistry,
    profile_key: str = "local_cpu",
    backend_keys: Sequence[str] = (),
) -> RuntimeProfile:
    profile = resolve_runtime_profile(registry, profile_key)
    requested_backend_keys = tuple(str(x) for x in (backend_keys or profile.backend_keys))
    registered: list[dict[str, str]] = []
    default_registered: tuple[str, str] | None = None

    for key in requested_backend_keys:
        spec = _find_backend_spec(registry, key)
        registration = _register_executor_backend(solver, spec)
        if registration is None:
            continue
        registered.append({"scope": registration[0], "backend": registration[1]})
        if registration[1] == profile.default_backend:
            default_registered = registration

    if default_registered is None and registered:
        first = registered[0]
        default_registered = (first["scope"], first["backend"])
    if default_registered is not None:
        _set_default_backend(solver, scope=default_registered[0], backend=default_registered[1])

    summary = {
        "profile": profile.as_dict(),
        "registered_executor_backends": list(registered),
        "effective_default_backend": None
        if default_registered is None
        else {"scope": default_registered[0], "backend": default_registered[1]},
    }
    setattr(solver, "l0_runtime_profile", profile)
    setattr(solver, "l0_runtime_summary", summary)
    return profile
