# optimization_strategies（已收敛）

“优化策略怎么选/怎么组”这类内容，在框架里最终会落到：

- 你在解决的具体问题长什么样（Problem）
- 你的解长什么样（RepresentationPipeline）
- 你想要什么倾向（Bias）
- 你怎么跑流程/并行/记录（Plugin）
- 你用哪套官方组合把它们一键粘起来（Wiring）

因此这份文档已收敛为下面三份“事实标准”，避免同一件事讲三遍：

- 端到端陪跑（从 0 到能跑）：`WORKFLOW_END_TO_END.md`
- 权威示例（参数命名/ctx keys/组合方式的事实标准）：`docs/AUTHORITATIVE_EXAMPLES.md`
- Catalog/Wiring Helpers（怎么搜组件、怎么一键 attach）：`docs/user_guide/catalog.md`

历史版本（不再维护，仅供考古）：

- `docs/_archive/optimization_strategies_old.md`