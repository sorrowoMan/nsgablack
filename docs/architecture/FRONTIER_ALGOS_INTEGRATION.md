# FRONTIER_ALGOS_INTEGRATION

This document explains how frontier algorithm ideas are decomposed into
Wiring Helpers + Adapters + Biases + Plugins in NSGABlack.

## 1) Multi-objective DFO / Trust-Region
- Adapter: `TrustRegionDFOAdapter`
- Plugins: `ModuleReportPlugin`, `BenchmarkHarnessPlugin`
- Bias (optional): `DynamicPenaltyBias`, `RobustnessBias`

## 2) Subspace Trust-Region (CUATRO_PLS style)
- Adapter: `TrustRegionSubspaceAdapter`
- Plugin: `SubspaceBasisPlugin` (PCA/SVD/SparsePCA/Cluster/Random)

## 3) Active Learning Surrogate
- Plugin: `SurrogateEvaluationPlugin`
- Bias: `UncertaintyExplorationBias`

## 4) Robust DFO
- Plugin: `MonteCarloEvaluationPlugin`
- Bias: `RobustnessBias`

## 5) Surrogate-Assisted EA
- Adapter: `VNSAdapter` (or other EA core)
- Plugin: `SurrogateEvaluationPlugin`

## 6) Surrogate Model Lab
- Plugin: `SurrogateEvaluationPlugin` (model_type variants)

## 7) Structure Prior
- Bias: `StructurePriorBias`

## 8) Multi-Fidelity Evaluation
- Plugin: `MultiFidelityEvaluationPlugin`

## 9) CVaR / Worst-case Risk
- Bias: `RiskBias` (CVaR or worst_case)
- Plugin: `MonteCarloEvaluationPlugin`

## 10) Dynamic Repair Pipeline
- Representation: `DynamicRepair`

Use `python -m nsgablack catalog search` to discover entries and demos.
