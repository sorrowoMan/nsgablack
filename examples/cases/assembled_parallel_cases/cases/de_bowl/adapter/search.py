"""仅装配 DE 的算法行为；没有外部并发循环。"""
from nsgablack.adapters import DifferentialEvolutionAdapter, DEConfig
from nsgablack.representation import UniformInitializer
from ..config import POPULATION_SIZE, BATCH_SIZE


def build_adapter():
    return DifferentialEvolutionAdapter(
        name="de_bowl", initializer=UniformInitializer(-4.0, 4.0),
        config=DEConfig(population_size=POPULATION_SIZE, batch_size=BATCH_SIZE,
                        differential_weight=0.7, crossover_rate=0.9, strategy="rand1bin"),
    )
