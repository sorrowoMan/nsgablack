# nested_trainer

候选级 ML Trainer Case。它使用 MLBlack `LearningProblem` 与 `ModelRepresentation`
把外层点解码成模型语义，并调用完整 `inner_solver` Case 校准内部参数，最终返回正式
MLBlack `TrainerResult`。
