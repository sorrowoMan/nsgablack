# L0 Task / Resource / Backend Architecture

This document describes the substrate contract behind Project-level orchestration. It separates three concepts that should not be collapsed:

- resources: CPU threads, device tokens, memory, services
- execution backend: local, process, worker queue, Ray, Kubernetes, cloud batch
- payload transport: inline JSON, artifact ref, object store ref

## Task Envelope

```python
TaskEnvelope(
    task_id="outer_search.eval.0007",
    task_type="nested_candidate_eval",
    payload={"candidate_ref": "snapshot://candidate/0007"},
    requirement=ResourceRequirement(threads=4, device_tokens=("logical-gpu-a",)),
    input_refs=("artifact://dataset/train",),
)
```

The task describes what it needs. It does not decide which physical worker or device it receives.

## Worker Descriptor

```python
WorkerDescriptor(
    worker_id="worker-a",
    executor_backend="local-process",
    capabilities=("python", "torch", "mlblack"),
    offer={"threads": 8, "device_tokens": ("logical-gpu-a",), "memory_mb": 32768},
)
```

Workers advertise capabilities and resource offers. The Project L0 runtime matches tasks to workers under policy.

## Task Result

```python
TaskResult.success(
    task_id="outer_search.eval.0007",
    objectives=[0.12, 3.4],
    violations=[0.0],
    metrics={"latency_ms": 842},
    artifact_refs=("artifact://runs/0007/report.json",),
    resource_context={
        "threads": 4,
        "device_tokens": ["logical-gpu-a"],
        "lease_id": "lease-0007",
    },
)
```

Task results must be auditable. Large objects should be returned as Snapshot or Artifact refs.

## Backend Boundary

| Backend | Responsibility | Not Responsible For |
| --- | --- | --- |
| local thread/process | run local tasks | deciding business objectives |
| worker queue | queue, heartbeat, result collection | interpreting candidates |
| Ray/K8s/cloud | distributed execution | bypassing Project L0 policy |
| artifact backend | store large data and reports | replacing ContextStore |
| transport backend | move payloads between workers | mutating task semantics |

## Project Integration

`project_config.py` declares pools and service backends. `run_project.py` builds the Project runtime, grants each Case a context, and records effective state.

Case code receives:

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    ...
```

The Case may attach backends or plugins from the context, but it should not allocate global resources by itself.

## Compatibility

Older helper APIs that accept raw thread counts or device strings should be treated as compatibility shims. New examples and tutorials should pass logical resource tokens through `ResourceContext`.
