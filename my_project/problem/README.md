# problem

**中文**
- 职责：问题层：目标、约束、变量维度与边界。
- 结构：`data/`（问题数据），`evaluation/`（L4 评估运行时配置）。
- 边界：只保留本层关切，不在此处隐藏跨层逻辑。
- I/O 约定：
  - 输入：数据源、参数、读取的 context 字段
  - 输出：返回对象、写入的 context 字段、副作用
  - 如使用 context，请声明
    `context_requires/context_provides/context_mutates/context_cache`。
- 最小示例：保留一个可运行文件，或说明入口路径。

**English**
- Responsibility: Problem layer: objective, constraints, variable dimension and bounds.
- Structure: `data/` (problem data), `evaluation/` (L4 evaluation config).
- Boundary: keep only this layer's concern; do not hide cross-layer logic here.
- I/O contract:
  - Input: data source, parameters, context fields read
  - Output: returned objects, context fields written, side effects
  - If context is used, declare
    `context_requires/context_provides/context_mutates/context_cache`.
- Minimal example: keep one runnable file, or document the entry path.
