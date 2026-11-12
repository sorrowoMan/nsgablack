# GA精英20 → VNS → GA：正式运行

Project run：`20261020T151220Z-1e7953d4ff`。

- 同一个标准hybrid_search Case，Project elite分组显式配置，L0为1 thread / 1 worker。
- GA种群24，运行2步；choose保留约束支配/拥挤度选择，从最终成员发布20个ga_elite。
- VNS按准确公共池名读取并冻结20个SolutionRef，每个执行起点与邻域共2步。
- 聚合refined保存40个硬接纳提案，返回GA重新求值竞争；不是20个最终精选结果的别名。
- 20个任务分别发布最终选择视图；该结果与聚合提案保留不同含义。
- 43次逻辑提交，GA48 + VNS40 + 返回40 = 128次求值，恰好用完128预算。
- 读取精英来源不求值；冻结引用逐项一致，原始反馈未被改写，成员年龄字段仍对齐。
- 默认population模式的81步/600次示例与原结果不覆盖；本轮文件独立保存到results/elite。

完整证据：results/elite/trace.json、summary.json、project_result.json。
解析最优点核对属于报告阶段独立计算，不冒充运行内持久证据。
