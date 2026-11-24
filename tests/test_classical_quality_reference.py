import numpy as np
import pytest

from benchmarks.classical_quality import reference_run


@pytest.mark.parametrize("algorithm,problem",[("nsga2","zdt1"),("nsga3","dtlz2"),("moead","zdt1")])
def test_independent_algorithm_uses_fixed_population_and_actual_budget(algorithm,problem):
    checkpoints=[]
    f,calls=reference_run(algorithm,problem,11,10,3,checkpoint=lambda:checkpoints.append(1))
    assert calls == 30
    assert f.shape == (10,3 if problem=="dtlz2" else 2)
    assert np.isfinite(f).all()
    assert checkpoints
