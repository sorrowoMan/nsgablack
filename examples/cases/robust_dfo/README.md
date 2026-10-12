# robust_dfo

实际组件组合：NoisySphere + TrustRegionDFOAdapter + MonteCarloEvaluationProviderPlugin(cvar)。最小化损失时取最差 25% 场景均值，作为 DFO 的原始稳健目标，不额外挂风险 Bias。

两个逻辑步骤、每个候选 8 次场景评估，仅用于接口与语义演示。

在本 Project 根运行 `python run_project.py --check --build-check` 和 `python run_project.py`。
资源由 Project L0 授权；Case 的 evaluation/、bias/、problem/ 保留各自定义。
