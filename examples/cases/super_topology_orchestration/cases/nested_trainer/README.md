# nested_trainer

候选级 ML Trainer Case。`LearningSolver + FixedCandidateAdapter` 将外层模型规格交给
`LearningProblem`；其 `fit.with_nested_solver/v1` Provider 调用完整 `inner_solver`
Case 校准参数，再返回模型与 Feedback。TrainerResult 来自统一生命周期。

`best_state` 保存 capacity/regularization，拟合后的 calibration 保存在模型 Artifact。
自身评估和内层求解各消耗一次预算。`training_summary` 与模型在同一 finalization
事务发布；summary 保存来自内层 Case 的实际资源、预算与取消链证据。
