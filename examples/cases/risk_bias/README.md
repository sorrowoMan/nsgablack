# risk_bias

实际组件组合：RiskCostProblem + TrustRegionDFOAdapter + MonteCarloEvaluationProviderPlugin(mean) + RiskBias。RiskBias 使用每个候选的 mc_mean/mc_std 软引导，原始均值评估仍保留。

两个逻辑步骤、每个候选 8 次场景评估，仅用于接口与语义演示。

在本 Project 根运行 `python run_project.py --check --build-check` 和 `python run_project.py`。
资源由 Project L0 授权；Case 的 evaluation/、bias/、problem/ 保留各自定义。
