from nsgablack.bias import BiasModule, DomainBias


class LinearSelectionBias(DomainBias):
    objective_independent = True
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self, weight):
        super().__init__("linear_selection", weight=weight, mandatory=False)

    def compute(self, x, context):
        return float(x[0])


def build_bias(weight):
    bias = BiasModule()
    if weight:
        bias.add(LinearSelectionBias(weight))
    return bias
