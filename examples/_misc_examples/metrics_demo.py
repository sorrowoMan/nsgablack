"""Metrics demo: Pareto filter, hypervolume, and IGD."""

import numpy as np

try:
    from nsgablack.utils.analysis import pareto_filter, hypervolume_2d, igd, reference_front_zdt1
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.utils.analysis import pareto_filter, hypervolume_2d, igd, reference_front_zdt1


def main():
    rng = np.random.default_rng(0)
    obj = rng.random((40, 2))
    pf = pareto_filter(obj)
    hv = hypervolume_2d(pf)
    ref = reference_front_zdt1(200)
    dist = igd(pf, ref)
    print("pareto size:", len(pf))
    print("hypervolume:", hv)
    print("igd:", dist)


if __name__ == "__main__":
    main()
