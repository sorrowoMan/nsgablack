# GA：成对变化、Pool 选择与每批精英维护

本 Case 与另外两个 Case 使用相同的母池来源、Snapshot 与事务。

- `paired_change(request, *, rng)` 对同一对父代共享一次掩码交叉，交付至多两个 `ChangeResult`。每个孩子分别派生 token 并保留精确父代引用。
- `choose_survivors(pool, *, count, rng)` 复用约束支配层和拥挤度，返回 `pool.take(indices)`。没有改成目标和选择。
- `maintain_elite(request, *, rng)` 在实际叶更新后运行一次，将本批硬接纳版本加入普通 elite 集合，按显式 raw 规则保留前20。

精英档案不等于 GA 最终种群；退出档案也不删除其他成员使用的候选。
正式运行与同次结果核对见 Project 的 `run_and_report.py`，不另建算法运行循环。

需要维护“历代最终成员”时，用同一 Case 的 `build_solver(config={"archive_source": "members"})`。
默认仍是 accepted，已有三 Case 报告保持原含义；members 模式绑定 `maintain_final_members`：
旧 elite 与本轮最终 request.members 归并，再按显式 raw 可行性/目标和选前20。
已接纳但被 GA 淘汰的后代不因此入档；已离开当前种群的历史精英仍可保留。
维护、成员版本与 Unit 在同一步提交，无额外求值；create=True 可显式创建缺失目标。
members 保留种群真实顺序与选择反馈；跨 root 合并使用显式 raw 规则，不自动合成方向分数。
