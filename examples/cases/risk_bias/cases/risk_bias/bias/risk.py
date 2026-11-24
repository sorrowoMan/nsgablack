from nsgablack.bias import BiasModule, RiskBias


def build_risk_bias():
    module = BiasModule()
    module.add(RiskBias(mode="cvar", alpha=0.2), weight=0.2)
    return module
