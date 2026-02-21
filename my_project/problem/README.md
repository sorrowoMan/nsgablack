# problem

**中文说明**
- 目录职责：Problem layer: objective, constraints, variable dimension and bounds.
- 边界要求：只放本层职责，不要在本目录隐藏跨层逻辑。
- 输入输出契约：
  - 输入：数据来源、参数、读取的 context 字段
  - 输出：返回对象、写入的 context 字段、副作用
  - 若使用 context，建议显式声明
    `context_requires/context_provides/context_mutates/context_cache`。
- 最小示例：至少保留一个可运行文件，或在此写清入口路径。

**English**
- Responsibility: Problem layer: objective, constraints, variable dimension and bounds.
- Boundary: keep only this layer's concern; do not hide cross-layer logic here.
- I/O contract:
  - Input: data source, parameters, context fields read
  - Output: returned objects, context fields written, side effects
  - If context is used, declare
    `context_requires/context_provides/context_mutates/context_cache`.
- Minimal example: keep one runnable file, or document the entry path.
