# Pool partition 正式运行

Project run：`20261020T091247Z-09b7ca0a97`。

- 标准ga_partition Case，正式Project partition分组，CPU 1 thread / 1 worker。
- 3次逻辑提交；求值预算260，实际100+80+80=260；partition新增求值0。
- 首次真实GA选择输入100，分为20精英与80剩余；后两次输入180，分为20与160。
- 普通choose每次调用partition一次，返回精英20与剩余前80，共100个生存成员。
- 精确位置与SolutionRef逐项对齐；selected/remaining互斥完备，source引用与候选值不变。
- 本例明确按raw可行性、违反量、目标和挑20；不是宣称等价于默认NSGA-II Pareto选择。
- 只读观察在提交后复核同一确定性分区，不额外调用Problem、不改变RNG或算法成员。

完整引用证据见results/ga_partition_baseline.json；观察文件不替代Authority或Artifact发布收据。
