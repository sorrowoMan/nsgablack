"""离线准备官方参考前沿文件；不是求解/benchmark 执行入口。

ZDT1/DTLZ2 由 pymoo 官方 Problem 生成；pymoo-data 并未提供这两个
问题的预计算文件，因此不伪造下载来源。测量时只读已固定的文件。
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np

from benchmarks.transparency_metrics import PYMOO_VERSION, REFERENCE_ROOT


def prepare(root=REFERENCE_ROOT):
    import pymoo
    from pymoo.problems import get_problem
    from pymoo.util.ref_dirs import get_reference_directions

    if pymoo.__version__ != PYMOO_VERSION:
        raise ValueError(f"prepare with pymoo=={PYMOO_VERSION}")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "nsgablack.official_reference_sets/v1", "pymoo_version": pymoo.__version__,
                "generation": "official pymoo Problem.pareto_front; no handwritten front equations",
                "sets": {}}
    configs = [
        ("zdt1", {"n_var": 8}, {"n_pareto_points": 1000}, [1.1, 11.0]),
        ("dtlz2", {"n_var": 8, "n_obj": 3},
         {"ref_dirs": get_reference_directions("das-dennis", 3, n_partitions=32)}, [3.0, 3.0, 3.0]),
    ]
    for name, arguments, front_args, hv_ref in configs:
        problem = get_problem(name, **arguments)
        values = problem.pareto_front(**front_args)
        path = root / f"{name}.pf"
        # Canonical CRLF matches the first published fixture bytes. A binary
        # stream prevents OS newline conversion from changing their SHA-256.
        with path.open("wb") as stream:
            np.savetxt(stream, values, fmt="%.17g", newline="\r\n")
        module_path = Path(inspect.getfile(type(problem)))
        generation_args = (front_args if name == "zdt1" else
                           {"reference_directions": {"method": "das-dennis", "n_dim": 3, "n_partitions": 32}})
        manifest["sets"][name] = {
            "file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "shape": list(values.shape), "origin": "official_generator_persisted_as_file",
            "serialization": {"encoding": "ascii", "line_ending": "CRLF", "float_format": "%.17g"},
            "problem_arguments": arguments, "front_arguments": generation_args,
            "generator_class": f"{type(problem).__module__}.{type(problem).__name__}",
            "generator_source_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
            "source_url": "https://github.com/anyoptimization/pymoo/tree/0.6.2/pymoo/problems",
            "hv_reference_point": hv_ref,
            "hv_reference_policy": "fixed before solving from fixture objective bounds; not fitted to either output",
        }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
