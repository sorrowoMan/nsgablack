"""描述符、格子、竞争和候选生成器均为显式组件。"""
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor, GridCells, MinimizeObjective, SequenceEmitter,
)

POINTS = ((.1, .1), (.4, .4), (.6, .4), (.6, .8), (.8, .2))


def build_adapter(settings):
    return MapElitesAdapter(MapElitesConfig(batch_size=settings.batch_size, random_seed=settings.seed),
        descriptor=IdentityDescriptor(), cells=GridCells(), competition=MinimizeObjective(),
        emitter=SequenceEmitter(POINTS))
