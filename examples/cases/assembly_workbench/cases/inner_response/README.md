# 内层条件响应

问题是固定 target 后最小化 `(y-target)**2`。默认 target=0.5。
初始化 y=target+0.5，第二步向 target 移动一半，所以默认两步的最终误差为 0.0625。
这是可手算的小例子，说明父条件、真实后继、反馈和返回值的关系。

父 Case 传 `inputs={"inner_task_payload": {"target": ..., "source": ...}}`；
标准 set_case_inputs 在运行前应用条件，不能把另一个 Case 的 Pool 当作当前池。
可直接运行 `python cases/inner_response/run_solver.py` 或带 --check。
无 Project runtime 的独立执行只输出本地 JSON，Artifact 来源标为 standalone，不伪造发布收据。
正式父调用发布 summary Artifact，保留 lineage、grant、独立 pool_id 和 payload。

默认输出 `results/inner_response/`；父调用通过 output_dir 将每次调用分开存储。

变化算子读取 VNS 的调用局部 vns_k，按 `1/(2+k)` 缩小到 target 的距离。
默认第一次邻域的 k=0，因此第二次评估确实是 y=target+0.25，而非重复基准的分数。

2026-10-21：`tests/test_assembly_workbench_nested.py` 五项实际运行测试通过；本 Case 的
`project doctor --strict --build --catalog-audit --profile framework-core` 为零错误、零警告。
