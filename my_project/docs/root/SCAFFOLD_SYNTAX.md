# 语法规范草案（规则 + 顺序）

装配层只做“注册与协调”，不在此处设定组件参数；参数在各层 registry，选择在 build_solver。
语义分层规则：L0/L1/L2/L3/L4 仅用于插件类，目录名不决定层级。

装配顺序（与 build_solver 调用一致）：
1) problem
2) pipeline
3) bias
4) solver core
5) adapter
6) L0 plugins（计算后端）
7) L4 plugins（评估接管）
8) L1/L2 plugins（观测/工程保障）
9) checkpoint（可选）

可执行判定句：
- 改记录/重放/审计/存储，不改搜索或评估语义 -> L1/L2
- 改搜索时序/策略路由/调度 -> L3
- 改评估来源或执行通路 -> L4

数据流锚点（不可打断）：
adapter.propose -> representation -> evaluation(problem 或 L4 provider) -> adapter.update -> plugin hooks -> snapshot/context

Stage-gate 提醒：
- Gate 1: problem 语义
- Gate 2: 层级归位
- Gate 3: catalog 组件筛选
- Gate 4: 装配落位（本文件）
