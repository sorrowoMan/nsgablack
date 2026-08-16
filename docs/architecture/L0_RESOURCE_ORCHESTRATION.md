# L0 Resource Orchestration

L0 is the resource and execution substrate shared by `nsgablack` and `mlblack`. It is not an algorithm layer and not a business semantics layer. It answers one question:

> What resources is this Project, Case, candidate evaluation, or nested run allowed to use?

## Core Rule

Resources are declared at Project level, requested by Cases, granted through `ResourceContext`, and audited by the effective runtime report.

```text
Project resource pool
  -> Case resource request
  -> ResourceAllocator
  -> ResourceLease
  -> ResourceContext
  -> Case build_solver(..., resource_context=...)
```

`nsgablack` and `mlblack` both consume this substrate. Neither semantic layer owns orchestration privately.

## Layer Boundaries

| Layer | L0 Responsibility |
| --- | --- |
| Shared Project substrate | declares global pools, grants leases, injects contexts, records audit |
| nsgablack semantic layer | declares search/evaluation requirements and uses the grant during optimization |
| mlblack semantic layer | declares training/evaluation requirements and uses the grant during fitting or inference |

Standalone `mlblack` use should still be a Project with a local L0 grant. Nested use simply derives the child grant from the parent Project.

## Standard Objects

| Object | Meaning |
| --- | --- |
| `ResourceOffer` | resources available to a Project runtime |
| `ResourceRequest` | resources requested by a Case or task |
| `ResourcePolicy` | conflict and fallback policy |
| `ResourceAllocator` | grants leases from offers and requests |
| `ResourceLease` | effective authorization result |
| `ResourceContext` | JSON-compatible payload injected into a Case |
| `LeaseStore` | active lease registry for local or distributed mutual exclusion |

Prefer logical device tokens such as `logical-gpu-a` over machine-local device names in docs and examples. The mapping belongs to the deployment/runtime layer.

## CPU and GPU Policy

| Resource | Default Policy | Reason |
| --- | --- | --- |
| CPU threads | clamp or auto | CPU can often be shared with controlled oversubscription |
| GPU device token | exclusive | training/evaluation jobs can easily conflict on memory and context |
| GPU memory | explicit when shared | memory is the usual failure boundary |
| process/Ray/worker | shared lease store | in-memory locks do not protect other processes |

Recommended default:

```python
ResourcePolicy(mode="strict", device_sharing="exclusive")
```

## ResourceContext Payload

An effective context should be small and serializable:

```json
{
  "namespace": "project.outer_search.trial_0007",
  "threads": 4,
  "device_tokens": ["logical-gpu-a"],
  "backend": "local",
  "lease_id": "lease-0007",
  "policy": {"failure": "soft", "device_sharing": "exclusive"}
}
```

The Case may translate `logical-gpu-a` into a framework-specific runtime object, but the translation is local and must be reported.

## Nested Cases

When an outer Case evaluates a candidate by calling an inner Case:

```text
outer Case request
  -> Project L0 child grant
  -> inner Case build_solver(..., resource_context=child_context)
  -> inner result + audit
  -> outer result projector
```

The inner Case cannot expand its resource scope. It can only use the grant, downgrade within the grant, or fail according to policy.

## Audit

Every formal run should record:

- requested resources
- granted resources
- actual backend
- actual device token or worker
- fallback reason, if any
- namespace and lease id
- artifact refs for reports and checkpoints

This makes nested optimization, multi-solver orchestration, and ML-backed evaluation reproducible.
