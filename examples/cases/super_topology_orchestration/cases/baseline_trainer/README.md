# baseline_trainer

并行基线阶段中的 ML Trainer Case。`LearningSolver + FixedCandidateAdapter`
运行一次正式训练评估，`LearningProblem` 使用 `NumericDataView` 和
`linear.least_squares.closed_form` Provider 拟合最小二乘模型。

`pipeline/` 编解码训练规格，`evaluation/` 负责拟合，`plugins/artifacts.py` 在
teardown 成功后将 `summary` 与 `best_model` 暂存到同一事务，由 CaseExecutor 最终发布。
