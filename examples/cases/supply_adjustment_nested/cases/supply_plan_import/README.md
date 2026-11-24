# 历史供应候选导入

在 Project 的 `component_overrides` 中显式指定 `old_authority` 与 `old_binding`；部署将该旧文件权威按原绝对路径只读挂载。本 Case 用旧生产者 Ledger 及物理字节验证，不调用旧 lease、不修改旧文件，也不使用新 HTTP profile 猜测旧输入位置。

通过当前生产数据加载器重新读取 BOM / SUPPLY，要求两份源 SHA 与旧方案完全一致。检查原发布身份、候选与事件顺序、整笔提前、今日库存、逐物料总量及场景摘要。`production_case_dir` 可选，仅供显式指定当前正式生产 Case；不会读取旧记录中的源绝对路径。

本 Case 不求解、不继承旧排程或旧分数。成功后由正常 finalization 发布 `candidate_plan`（`supply_adjustment_nested.candidate_plan/v1`），携带新发布身份及 `derived_from` 原权威、原绑定、原字节摘要。

下游 evaluation-only 供应 Case 用 `input_artifacts={"candidate_plan": "导入阶段.supply_plan_import.candidate_plan"}` 读取该输入，产生新的候选身份并重新调用生产 Case。旧 same-authority `joint_summary/v1` 输入继续有效。
