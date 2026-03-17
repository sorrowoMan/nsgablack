# plugins

**中文**
- 职责：工程层：日志、并行、回放、可视化等运行能力。
- 结构：`observability/`（L1/L2），`checkpoint/`（L1/L2），其余插件可继续放在本目录。
- 边界：只保留本层关切，不在此处隐藏跨层逻辑。
- I/O 约定：
  - 输入：数据源、参数、读取的 context 字段
  - 输出：返回对象、写入的 context 字段、副作用
  - 如使用 context，请声明
    `context_requires/context_provides/context_mutates/context_cache`。
- 最小示例：保留一个可运行文件，或说明入口路径。

**English**
- Responsibility: Engineering layer: logging, parallelism, replay, visualization.
- Structure: `observability/` (L1/L2), `checkpoint/` (L1/L2), other plugins can stay here.
- Boundary: keep only this layer's concern; do not hide cross-layer logic here.
- I/O contract:
  - Input: data source, parameters, context fields read
  - Output: returned objects, context fields written, side effects
  - If context is used, declare
    `context_requires/context_provides/context_mutates/context_cache`.
- Minimal example: keep one runnable file, or document the entry path.
