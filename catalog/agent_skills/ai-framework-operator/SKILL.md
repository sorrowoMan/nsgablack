---
name: ai-framework-operator
description: Operate, audit, and evolve the current blackbase + nsgablack + mlblack framework stack. Use for architecture analysis, repository ownership decisions, Project/Case/Scaffold and L0 resource work, optimization or ML capability routing, cross-framework Cases, Catalog/Doctor audits, and framework implementation planning. Also use when deciding whether a feature belongs in blackbase, nsgablack, mlblack, or an external provider/bridge. Do not use the retired AI Framework Operator Shell or its HTTP API.
---

# Black Framework Stack Operator

Work directly with the current repositories and their formal public surfaces. Do not start or call the retired `ai_framework_operator_shell`, port 8765, session API, `88code` provider, or `operator_api.py`.

When the native `black-framework` MCP is available, use `framework_context` for versioned foundations and declared capabilities; use `list_projects` / `open_project` for saved Project state and a revision-bound session. Prefer `framework_api` for concrete signatures and fields, with focused source reads as needed. These tools reuse the current framework implementations, not another model. Source changes invalidate the old session. `check_project_edit` is static unless a trusted host validator explicitly supplies a matching execution receipt. Editing and running continue through authorized host tools and formal Project/Case/L0 entrypoints. See the current repository's `docs/user_guide/FRAMEWORK_MCP_CN.md` for configuration; do not assume connection implies context loading or new permissions.


核对 `framework_context.framework_source` 的实际源码根与代表文件指纹，并与宿主实际运行导入位置一致；同版本号不等于同一工作树。MCP注册入口应使用隔离Python导入或稳定运行目录，避免被当前Project同名包遮蔽；加载了另一份框架时不能把查询和运行证据混用。

## Resolve the live stack

Resolve the repositories from the active workspace first, then the installed package source locations or the MCP source evidence. Do not assume another machine uses a stored local path. If actual source editing is required and only an installed package is available, establish the repository root before editing it.

Before making claims or changes:

1. Read the applicable `AGENTS.md` files completely.
2. Read the current repository `README.md` and `pyproject.toml` when package boundaries or installation matter.
3. Inspect Git status without modifying unrelated user work.
4. Treat documentation and implementation as separate evidence when they disagree.

Do not rely on paths, commands, templates, or APIs copied into this skill when the live repository gives a newer rule.

## Classify ownership first

Route work by semantics, not by which repository is already open:

- `blackbase`: shared Project/Case/Scaffold substrate, Context/Snapshot contracts, ResourceContext and L0 grants, pipeline slot kernel, shared plugin lifecycle, cross-Case payload types.
- `nsgablack`: optimization and search semantics, Solver lifecycle, candidate search, Adapter strategy, objectives and constraints, Pareto/frontier behavior, optimization audit.
- `mlblack`: ML semantics, DataView, Spec, Codec, Head, Trainer, Provider, Artifact, training/evaluation reports, symbolic learning semantics.
- external provider or bridge: numerical solvers, simulators, databases, object stores, vector indexes, Ray/Kubernetes/cloud runtimes, and other domain backends.

If a feature spans repositories, define the shared contract in `blackbase` and keep framework-specific behavior on its owning side. Do not let nsgablack import mlblack trainer/provider internals or let mlblack recreate a private Project/L0 allocator.

## Select the workflow

### Architecture, diagnosis, or status

- Default to read-only inspection.
- Trace one end-to-end path before judging a subsystem: public entry -> builder -> runtime -> state/artifact output.
- Separate implemented behavior, documented intent, and executed evidence.
- Report repository ownership, contract gaps, and the smallest closure sequence.
- Do not edit code merely because a likely root cause is visible.

### Implementation or migration

- Confirm that the user authorized writes and any required validation commands.
- Make the smallest coherent change in the owning repository.
- Preserve compatibility forwarders only when the live migration policy requires them.
- Update contract definitions, Doctor rules, Catalog entries, scaffold templates, and docs together when one public rule changes.
- Never hide cross-framework glue in examples. Use formal Case payloads, component overrides, ResourceContext, artifacts, and result payloads.

### Project and Case work

- Use the live Project -> Case -> Standard Scaffold contract from repository instructions.
- Keep cross-Case order, fanout, and resource allocation at Project level.
- Keep each Case independently buildable, runnable, and auditable.
- Pass effective ResourceContext from Project L0 into the Case; a Case declares requirements but does not allocate global resources.
- Verify that check output reports the effective runtime context and actually assembled components, not configuration intent alone.

### Data, optimization, and ML routing

- Treat operations research as optimization without requiring a target column.
- Require decision variables, objectives, and constraints before inventing an OR Case.
- Require a target only for supervised prediction/training, not for unsupervised ML or data profiling.
- Keep prediction as an inner model when it supports a larger optimization workflow.
- Build reusable work through formal framework Cases rather than a private chat/session workspace.

## Validation and evidence

Honor every repository authorization gate before running Doctor, Catalog, tests, benchmarks, builds, or bulk scripts.

When authorized:

- Use `framework-core` for nsgablack architecture and contract audits.
- Compare `default` and `framework-core` when Catalog behavior or discoverability changes.
- Run focused contract tests before broad suites.
- Validate single-candidate, population, evaluation-provider short-circuit, and Snapshot paths after evaluation changes.
- Validate Project check/build-check output after scaffold or ResourceContext changes.
- Use the repository-specific Doctor instead of assuming nsgablack and mlblack expose identical commands.

Never present a capability as verified unless the validating command was actually run successfully. Record the command, scope, and result. Label source-only conclusions as static analysis.

## Safety and reporting

- Preserve dirty worktrees and unrelated changes.
- Do not expose secrets, environment values, credentials, or provider keys.
- Lead with the outcome, then state ownership, evidence, verification status, and next action.
- Call out contract split-brain explicitly when AGENTS, templates, Doctor, Catalog, and examples disagree.
- Prefer root-cause closure over adding another compatibility layer.
