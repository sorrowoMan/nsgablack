# optimization_strategies（已收敛）

“优化策略怎么选/怎么组”这类内容，在框架里最终会落到：

- 你在解决的具体问题长什么样（Problem）
- 你的解长什么样（RepresentationPipeline）
- 你想要什么倾向（Bias）
- 你怎么跑流程/并行/记录（Plugin）
- 你用哪套官方组合把它们一键粘起来（Wiring）

因此这份文档已收敛为下面三份“事实标准”，避免同一件事讲三遍：

- 端到端陪跑（从 0 到能跑）：`docs/standard_scaffold_tutorial/01_create_and_run.md`
- 示例标准落点与迁移政策：`docs/project/AUTHORITATIVE_EXAMPLES.md`
- Catalog/Wiring Helpers（怎么搜组件、怎么一键 attach）：`docs/user_guide/catalog.md`

历史版本不再维护；如需考古请查看 Git 历史。
