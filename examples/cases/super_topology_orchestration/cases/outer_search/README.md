# outer_search

外层多目标 Solver Case。探索阶段使用多 role / 多 unit 路由，随后串行执行 VNS、
Trust Region 和 DE；每个候选都通过共享 Case 协议调用 `nested_trainer`。
