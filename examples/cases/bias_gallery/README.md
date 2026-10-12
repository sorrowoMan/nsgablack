# bias_gallery

本 Case 演示 **Unit 结构、Adapter 决策、Bias 偏好** 的装配关系：

- Adapter：`NSGA2Adapter`，拥有 PopulationUnit。
- BiasModule：`UnitPreferenceBias(PopulationDiversityPreference)` 读取 `("bias_gallery", "search")` 实例视图；`TabuSearchBias` 记录已提交步骤中接纳的提案。
- 多样性奖励只改变选择目标，Problem 原始目标仍保留；禁忌评分不在 evaluate 时更新历史。
- 初始化成员尚无 token 时不伪造身份。只有已知相同 token 才可排除自身，重复数值仍计算为零距离。
- PopulationUnit 保留候选并扩展算法信息；NSGA-II 的选择排序使用 UnitFeature 按依赖维护，缓存不进入 checkpoint。参考视图的距离矩阵可按需请求；本例逐候选新颖性不强制建立平方级缓存。见 [Unit 特征维护](../../../docs/architecture/UNIT_FEATURES_CN.md)。

偏好工厂在 `cases/bias_gallery/bias/domain/example_bias.py`，正式入口在组装 Adapter 后绑定它。自定义替换 Adapter 时须提供兼容 population preference view，或通过组件覆盖提供自己的 BiasModule；不自动合并异质 Unit。

整体 Unit/结构变化比较接口见 [Unit 与偏好契约](../../../docs/architecture/UNIT_PREFERENCE_CONTRACT_CN.md)。

这是一个遵循统一 **Project -> Case -> Standard Scaffold** 结构的 nsgablack 示例 Project。

## 运行

~~~powershell
python examples/cases/bias_gallery/run_project.py --check
python examples/cases/bias_gallery/run_project.py
~~~

默认 Project 配置是可执行的 smoke profile；更大的研究规模应通过 Case 配置或显式组件覆盖启用。

## 编排边界

- **run_project.py**：Project 级统一入口。
- **project_config.py**：阶段、Case 顺序、L0 资源请求和组件覆盖。
- **cases/**：可独立装配、检查并由 Project 调用的标准 Case。
- Project L0 负责资源授权；Case 只消费生效后的 **ResourceContext**。

## Cases

- `bias_gallery`

每个 Case 的算法语义、Problem、Pipeline、Adapter 和 Plugin 组合请查看对应 Case 目录。
