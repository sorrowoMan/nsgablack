# FRONTIER_ALGOS_INTEGRATION

This document explains how frontier algorithm ideas are decomposed into
Wiring Helpers + Adapters + Biases + Plugins in NSGABlack.

## 1) Multi-objective DFO / Trust-Region
- Adapter: `TrustRegionDFOAdapter`
- Plugins: `ModuleReportPlugin`, `BenchmarkHarnessPlugin`
- Bias (optional): `DynamicPenaltyBias`, `RobustnessBias`

## 2) Subspace Trust-Region (CUATRO_PLS style)
- Adapter: `TrustRegionSubspaceAdapter`

## 3) Active Learning Surrogate
- Plugin: `SurrogateEvaluationProviderPlugin`
- Bias: `UncertaintyExplorationBias`

## 4) Robust DFO
- Plugin: `MonteCarloEvaluationProviderPlugin`
- Bias: `RobustnessBias`

## 5) Surrogate-Assisted EA
- Adapter: `VNSAdapter` (or other EA core)
- Plugin: `SurrogateEvaluationProviderPlugin`

## 6) Surrogate Model Lab
- Plugin: `SurrogateEvaluationProviderPlugin` (model_type variants)

## 7) Structure Prior
- Bias: `StructurePriorBias`

## 8) Multi-Fidelity Evaluation
- Plugin: `MultiFidelityEvaluationProviderPlugin`

## 9) CVaR / Worst-case Risk
- Bias: `RiskBias` (CVaR or worst_case)
- Plugin: `MonteCarloEvaluationProviderPlugin`

## 10) Dynamic Repair Pipeline
- Representation: `DynamicRepair`

Use `python -m nsgablack catalog search` to discover entries and demos.
