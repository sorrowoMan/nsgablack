# runtime

L0 project entrypoint for runtime resources and execution backends.

Default workflow:

1. Keep `local_cpu` while modeling, pipeline, adapter and plugins are still changing.
2. Use `runtime.graph.build_execution_plan_graph(solver)` to inspect the static stage tree.
3. Add or switch runtime profiles only for stages that need thread/process/GPU/Redis/Ray semantics.
4. Record effective worker, lease, `ResourceContext` and artifact refs in runtime reports.

Do not put objective, constraint, adapter strategy or business report logic here.
