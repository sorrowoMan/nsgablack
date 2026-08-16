# 06. L0 Parallel Resource Patterns

L0 is the shared resource and execution substrate. It is not a small “thread count” option. It controls how Projects authorize CPU, device tokens, memory, services, workers, queues, and artifacts across Cases.

## 1. Separate Resources From Backends

| Concept | Examples | Meaning |
| --- | --- | --- |
| resource | CPU threads, device token, memory | what the task is allowed to consume |
| executor backend | local, process, Ray, K8s, cloud batch | where the task runs |
| state backend | memory, SQLite, Redis | how leases and task states are tracked |
| artifact backend | filesystem, S3, object store | where large outputs go |
| transport | inline payload, artifact ref, object ref | how data crosses worker boundaries |

Do not mix these into one `backend` string. A Case may run on a Ray executor while consuming no GPU, or run locally while consuming a Project-granted device token.

## 2. Project-Level Declaration

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 16,
        "device_tokens": ("logical-gpu-a", "logical-gpu-b"),
        "memory_mb": 65536,
    },
    "policy": {
        "device_sharing": "exclusive",
        "failure": "soft",
    },
}

resource_requests = {
    "outer_search": {"threads": 4},
    "inner_learning": {"threads": 4, "device_tokens": ("logical-gpu-a",)},
}
```

The device token is logical. Deployment code may map it to a concrete machine device, but Case docs and examples should stay at the token level.

## 3. Case-Level Runtime

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    runtime = RuntimeProfile.from_context(resource_context)
    solver = make_solver(config)
    attach_resource_audit(solver, runtime)
    attach_optional_parallel_backend(solver, runtime)
    return solver
```

Case runtime code should:

- read the grant
- clamp local settings to the grant
- attach optional backends
- report effective behavior
- fail or downgrade according to policy

It should not claim new global resources.

## 4. Common Patterns

### Local CPU

Use this for first smoke tests and most lightweight examples.

```python
resource_requests = {
    "case_a": {"threads": 2}
}
```

### Multi-Case Fanout

Use Project orchestration when multiple solvers or trainers run side by side:

```python
stages = [
    {"name": "search_and_fit", "parallel": ["outer_search", "inner_learning"]},
]
```

The Project runtime grants each Case separately and records effective contexts.

### Nested Evaluation

```text
outer candidate
  -> child ResourceRequest
  -> Project L0 child grant
  -> inner Case
  -> structured result
```

The child request may ask for fewer resources than the parent grant, but it cannot exceed the Project pool or policy.

### Worker Queue

Use a worker queue when evaluations are expensive or distributed:

```python
L0 = {
    "backend": "worker_queue",
    "queue": {"kind": "redis", "name": "nsgablack.tasks"},
    "artifact_backend": {"kind": "filesystem", "root": "runs/artifacts"},
}
```

Queue backends schedule tasks; they do not change candidate or ML semantics.

## 5. Resource Reports

Every formal run should include:

```json
{
  "case": "inner_learning",
  "requested": {"threads": 4, "device_tokens": ["logical-gpu-a"]},
  "granted": {"threads": 4, "device_tokens": ["logical-gpu-a"]},
  "effective_backend": "local",
  "fallback": null,
  "lease_id": "lease-0007",
  "namespace": "project.inner_learning.0007"
}
```

The report is part of the run surface, not optional debug text.

## 6. Migration Rules

| Old habit | Current rule |
| --- | --- |
| example script sets local device directly | Project grants a logical device token |
| trainer starts its own global scheduler | Case consumes `ResourceContext` |
| multi-solver loop inside one script | Project with multiple Cases |
| large payload in context | Snapshot or Artifact ref |
| backend string contains resource, executor, and service | split resource, executor, state, artifact, and transport config |

## 7. Minimum Checklist

- Project declares a resource pool.
- Each Case declares a request.
- `build_solver` accepts `resource_context`.
- run summary prints requested and effective resources.
- nested Cases receive child contexts.
- artifacts and large results are refs, not inline context blobs.
