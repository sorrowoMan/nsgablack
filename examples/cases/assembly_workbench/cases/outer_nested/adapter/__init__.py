from nsgablack.adapters import NSGA2Adapter

def build_adapter():
    return NSGA2Adapter(name="outer_ga", population_size=2, offspring_size=2)
