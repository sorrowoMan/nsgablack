from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, FixedRBFPosterior, LowerConfidenceBound, GridAcquisitionOptimizer)


def build_adapter():
    return BayesianOptimizationAdapter(model=FixedRBFPosterior(),
        acquisition=LowerConfidenceBound(beta=2.0), optimizer=GridAcquisitionOptimizer())
