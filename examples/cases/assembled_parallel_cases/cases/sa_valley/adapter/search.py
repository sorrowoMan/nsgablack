"""SA 温度控制接受规则，变异组件根据局部 mutation_sigma 生成邻居。"""
from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
from nsgablack.representation import UniformInitializer, ContextGaussianMutation


def build_adapter():
    return SimulatedAnnealingAdapter(
        name="sa_valley", initializer=UniformInitializer(-4.0, 4.0),
        mutator=ContextGaussianMutation(base_sigma=0.65),
        config=SAConfig(batch_size=1, initial_temperature=1.0, cooling_rate=0.94,
                        min_temperature=1e-6, base_sigma=0.65, random_seed=29),
    )
