# 本 Project 全部代码与配置

生成日期：2026-10-19。以下是实际文件的阅读快照。程序源码是权威；修改代码请编辑原文件。
包含全部项目 Python、本地 Catalog TOML、Case 标记和忽略配置；排除运行结果、缓存和本地 `.blackbase/`。
框架已有组件的完整实现见 [COMPONENTS.md](COMPONENTS.md)，没有复制为第二份 Case 实现。

共 44 个源码／配置文件。说明见 [README.md](README.md)，真实结果见 [RESULTS.md](RESULTS.md)。

## 文件索引

- [.gitignore](.gitignore)
- [_bootstrap.py](_bootstrap.py)
- [cases/__init__.py](cases/__init__.py)
- [cases/de_bowl/.case](cases/de_bowl/.case)
- [cases/de_bowl/__init__.py](cases/de_bowl/__init__.py)
- [cases/de_bowl/adapter/__init__.py](cases/de_bowl/adapter/__init__.py)
- [cases/de_bowl/adapter/search.py](cases/de_bowl/adapter/search.py)
- [cases/de_bowl/bias/__init__.py](cases/de_bowl/bias/__init__.py)
- [cases/de_bowl/build_solver.py](cases/de_bowl/build_solver.py)
- [cases/de_bowl/build_trainer.py](cases/de_bowl/build_trainer.py)
- [cases/de_bowl/catalog/entries/problem.toml](cases/de_bowl/catalog/entries/problem.toml)
- [cases/de_bowl/config.py](cases/de_bowl/config.py)
- [cases/de_bowl/evaluation/__init__.py](cases/de_bowl/evaluation/__init__.py)
- [cases/de_bowl/pipeline/__init__.py](cases/de_bowl/pipeline/__init__.py)
- [cases/de_bowl/pipeline/main.py](cases/de_bowl/pipeline/main.py)
- [cases/de_bowl/plugins/__init__.py](cases/de_bowl/plugins/__init__.py)
- [cases/de_bowl/problem/__init__.py](cases/de_bowl/problem/__init__.py)
- [cases/de_bowl/problem/bowl.py](cases/de_bowl/problem/bowl.py)
- [cases/de_bowl/run_solver.py](cases/de_bowl/run_solver.py)
- [cases/de_bowl/run_trainer.py](cases/de_bowl/run_trainer.py)
- [cases/de_bowl/runtime/__init__.py](cases/de_bowl/runtime/__init__.py)
- [cases/de_bowl/solver/__init__.py](cases/de_bowl/solver/__init__.py)
- [cases/sa_valley/.case](cases/sa_valley/.case)
- [cases/sa_valley/__init__.py](cases/sa_valley/__init__.py)
- [cases/sa_valley/adapter/__init__.py](cases/sa_valley/adapter/__init__.py)
- [cases/sa_valley/adapter/search.py](cases/sa_valley/adapter/search.py)
- [cases/sa_valley/bias/__init__.py](cases/sa_valley/bias/__init__.py)
- [cases/sa_valley/build_solver.py](cases/sa_valley/build_solver.py)
- [cases/sa_valley/build_trainer.py](cases/sa_valley/build_trainer.py)
- [cases/sa_valley/catalog/entries/problem.toml](cases/sa_valley/catalog/entries/problem.toml)
- [cases/sa_valley/config.py](cases/sa_valley/config.py)
- [cases/sa_valley/evaluation/__init__.py](cases/sa_valley/evaluation/__init__.py)
- [cases/sa_valley/pipeline/__init__.py](cases/sa_valley/pipeline/__init__.py)
- [cases/sa_valley/pipeline/main.py](cases/sa_valley/pipeline/main.py)
- [cases/sa_valley/plugins/__init__.py](cases/sa_valley/plugins/__init__.py)
- [cases/sa_valley/problem/__init__.py](cases/sa_valley/problem/__init__.py)
- [cases/sa_valley/problem/valley.py](cases/sa_valley/problem/valley.py)
- [cases/sa_valley/run_solver.py](cases/sa_valley/run_solver.py)
- [cases/sa_valley/run_trainer.py](cases/sa_valley/run_trainer.py)
- [cases/sa_valley/runtime/__init__.py](cases/sa_valley/runtime/__init__.py)
- [cases/sa_valley/solver/__init__.py](cases/sa_valley/solver/__init__.py)
- [project_config.py](project_config.py)
- [run_and_report.py](run_and_report.py)
- [run_project.py](run_project.py)

## 1. [.gitignore](.gitignore)

源文件 SHA256：`dc0c67e07f875b4900c7e303a52bcb69d7c9550fb9fa8a331d9c89f968a16f6c`；3 行。

````text
.blackbase/
__pycache__/
*.pyc
````

## 2. [_bootstrap.py](_bootstrap.py)

源文件 SHA256：`873ea5f2cc48966f69c16f11dde4fef3987b214aa8f9a0f62c435d8aa9269ad4`；22 行。

````python
"""Path bootstrap that ensures project/framework imports work."""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_importable():
    """Add project root and framework parents to sys.path."""
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Ensure sibling framework packages are discoverable
    _nsga_parent = root.parent
    if (_nsga_parent / "nsgablack").is_dir() and str(_nsga_parent) not in sys.path:
        sys.path.insert(0, str(_nsga_parent))


def bootstrap():
    """Backward-compatible bootstrap entry used by run_project.py."""
    ensure_importable()
````

## 3. [cases/__init__.py](cases/__init__.py)

源文件 SHA256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`；0 行。

````python

````

## 4. [cases/de_bowl/.case](cases/de_bowl/.case)

源文件 SHA256：`a22a4b6bc57ee18868d19342674d1d86560b51d3f30eff89dbb2beb1873a17e2`；3 行。

````text
name = de_bowl
kind = solver
framework = nsgablack
````

## 5. [cases/de_bowl/__init__.py](cases/de_bowl/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 6. [cases/de_bowl/adapter/__init__.py](cases/de_bowl/adapter/__init__.py)

源文件 SHA256：`db99e968cb9856f97a8a93f088ab340b489a09b7014baccbbe2fab6041ff49ed`；2 行。

````python

from .search import build_adapter
````

## 7. [cases/de_bowl/adapter/search.py](cases/de_bowl/adapter/search.py)

源文件 SHA256：`2850cfaa0427efe89eee57f9c9ae29b2cb49b28953b63d4f832242aab3875316`；12 行。

````python
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
````

## 8. [cases/de_bowl/bias/__init__.py](cases/de_bowl/bias/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 9. [cases/de_bowl/build_solver.py](cases/de_bowl/build_solver.py)

源文件 SHA256：`5972ebcede925512079e3e5990d8b9ec74f538c02192b669dbcacfd2cb0222e1`；18 行。

````python
"""唯一 Case 装配入口；资源来自 Project 授权。"""
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import SEED, MAX_STEPS
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(problem=build_problem(), adapter=build_adapter(),
                             representation_pipeline=build_pipeline(), resource_context=resource_context,
                             plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(options.get("seed", SEED)))
    solver.set_max_steps(int(options.get("max_steps", MAX_STEPS)))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
````

## 10. [cases/de_bowl/build_trainer.py](cases/de_bowl/build_trainer.py)

源文件 SHA256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`；1 行。

````python
from .build_solver import build_solver as build_trainer
````

## 11. [cases/de_bowl/catalog/entries/problem.toml](cases/de_bowl/catalog/entries/problem.toml)

源文件 SHA256：`8004b699847f4bfca027e09e781ed3f115e5714cb01e6ac551f4116ebaddd270`；17 行。

````toml
[[entry]]
key = "project.problem.de_bowl"
title = "BowlProblem"
kind = "tool"
import_path = "problem.bowl:BowlProblem"
tags = ["project", "example", "problem", "de", "quadratic"]
summary = "DE独立Case的二维球面目标，已知最优点[1,-2]，原始最优值0。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["定义目标和盒约束违反量，不读取算法状态，不写共享context。"]
use_when = ["检查独立DE Case装配和解析目标时。"]
minimal_wiring = ["from cases.de_bowl.problem.bowl import BowlProblem", "problem = BowlProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.de_bowl.build_solver:build_solver"
````

## 12. [cases/de_bowl/config.py](cases/de_bowl/config.py)

源文件 SHA256：`bfca8083db9ec0a2c6daa0fbab54e72c0ce5219a958f01d058bbb6eab532c04c`；5 行。

````python
"""本 Case 的搜索预算；不是母池容量。"""
SEED = 17
MAX_STEPS = 16
POPULATION_SIZE = 12
BATCH_SIZE = 12
````

## 13. [cases/de_bowl/evaluation/__init__.py](cases/de_bowl/evaluation/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 14. [cases/de_bowl/pipeline/__init__.py](cases/de_bowl/pipeline/__init__.py)

源文件 SHA256：`b7fb51f3c2989875ac0734a66f59ed8ced326eb62d427fc0d2f96567fe95ae98`；1 行。

````python
from .main import build_pipeline
````

## 15. [cases/de_bowl/pipeline/main.py](cases/de_bowl/pipeline/main.py)

源文件 SHA256：`2273c003fe4b20026796f939f0d56a4fdd777af138263278bdf2a9757c940979`；6 行。

````python
"""问题管线只做边界修复；DE 变化由自己的差分规则负责。"""
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4.0, 4.0))
````

## 16. [cases/de_bowl/plugins/__init__.py](cases/de_bowl/plugins/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 17. [cases/de_bowl/problem/__init__.py](cases/de_bowl/problem/__init__.py)

源文件 SHA256：`796dac9b3378777369b8a8d7cadc783845399b50d1e7aaca4ba79d8d7802b5d4`；5 行。

````python
from .bowl import BowlProblem


def build_problem():
    return BowlProblem()
````

## 18. [cases/de_bowl/problem/bowl.py](cases/de_bowl/problem/bowl.py)

源文件 SHA256：`eef2b6f995113d04b353aa6db7c7359e9db4dc120b0f09b6e87193283d952883`；20 行。

````python
"""DE 独立求解二维球面问题，已知最优点 [1, -2]。"""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class BowlProblem(BlackBoxProblem):
    optimum = (1.0, -2.0)

    def __init__(self):
        super().__init__(name="DE 二维球面", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] - 1.0) ** 2 + (x[1] + 2.0) ** 2)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
````

## 19. [cases/de_bowl/run_solver.py](cases/de_bowl/run_solver.py)

源文件 SHA256：`ab283d8f4ae5229c5ed6e690ffba71ddfd54587d9d880bbb49da3558ccc24db9`；17 行。

````python
"""
CLI entry point for running the solver.

Usage:
    python run_solver.py
    python run_solver.py --check
"""

from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
````

## 20. [cases/de_bowl/run_trainer.py](cases/de_bowl/run_trainer.py)

源文件 SHA256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`；4 行。

````python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
````

## 21. [cases/de_bowl/runtime/__init__.py](cases/de_bowl/runtime/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 22. [cases/de_bowl/solver/__init__.py](cases/de_bowl/solver/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 23. [cases/sa_valley/.case](cases/sa_valley/.case)

源文件 SHA256：`d5ad20efdd33d2ab7c6f1b7b3f0076f2a874a46d6d16a26c4201ba39641f8b46`；3 行。

````text
name = sa_valley
kind = solver
framework = nsgablack
````

## 24. [cases/sa_valley/__init__.py](cases/sa_valley/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 25. [cases/sa_valley/adapter/__init__.py](cases/sa_valley/adapter/__init__.py)

源文件 SHA256：`db99e968cb9856f97a8a93f088ab340b489a09b7014baccbbe2fab6041ff49ed`；2 行。

````python

from .search import build_adapter
````

## 26. [cases/sa_valley/adapter/search.py](cases/sa_valley/adapter/search.py)

源文件 SHA256：`b52b8a8db299b0ad12e3295c88f5732173c011e7b3b96448770640a1b969499c`；12 行。

````python
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
````

## 27. [cases/sa_valley/bias/__init__.py](cases/sa_valley/bias/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 28. [cases/sa_valley/build_solver.py](cases/sa_valley/build_solver.py)

源文件 SHA256：`bdc1b594b0900eb9d9b73e47c8b6787530623ac2c601078545a0e35c140c7877`；18 行。

````python
"""SA 的独立 Solver；不与 DE 共享运行状态或母池。"""
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import SEED, MAX_STEPS
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(problem=build_problem(), adapter=build_adapter(),
                             representation_pipeline=build_pipeline(), resource_context=resource_context,
                             plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(options.get("seed", SEED)))
    solver.set_max_steps(int(options.get("max_steps", MAX_STEPS)))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
````

## 29. [cases/sa_valley/build_trainer.py](cases/sa_valley/build_trainer.py)

源文件 SHA256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`；1 行。

````python
from .build_solver import build_solver as build_trainer
````

## 30. [cases/sa_valley/catalog/entries/problem.toml](cases/sa_valley/catalog/entries/problem.toml)

源文件 SHA256：`c8082afcaf3820c39977f0b0f980d28770c9e4b5be80844fc7c626943a6e13e7`；17 行。

````toml
[[entry]]
key = "project.problem.sa_valley"
title = "ValleyProblem"
kind = "tool"
import_path = "problem.valley:ValleyProblem"
tags = ["project", "example", "problem", "sa", "quadratic"]
summary = "SA独立Case的各向异性二次谷地，已知最优点[-1.5,0.75]，原始最优值0。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["仅定义当前Case的目标和原始约束，不与DE共享Problem或解池。"]
use_when = ["检查独立SA Case装配和小预算结果时。"]
minimal_wiring = ["from cases.sa_valley.problem.valley import ValleyProblem", "problem = ValleyProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.sa_valley.build_solver:build_solver"
````

## 31. [cases/sa_valley/config.py](cases/sa_valley/config.py)

源文件 SHA256：`0e5f858d181f9b1fb7788b2a16a05b0681a280e710c977ffb58cc3f118c46e5d`；3 行。

````python
"""SA 是单轨迹；步数与 DE 的种群规模没有换算关系。"""
SEED = 29
MAX_STEPS = 40
````

## 32. [cases/sa_valley/evaluation/__init__.py](cases/sa_valley/evaluation/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 33. [cases/sa_valley/pipeline/__init__.py](cases/sa_valley/pipeline/__init__.py)

源文件 SHA256：`b7fb51f3c2989875ac0734a66f59ed8ced326eb62d427fc0d2f96567fe95ae98`；1 行。

````python
from .main import build_pipeline
````

## 34. [cases/sa_valley/pipeline/main.py](cases/sa_valley/pipeline/main.py)

源文件 SHA256：`ca9b50f5710ec4a4947a6be6ec7bb4b9881a36680e708a4e17bd74e4a1c18368`；6 行。

````python
"""与 DE 独立的管线实例；只装配问题边界修复。"""
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4.0, 4.0))
````

## 35. [cases/sa_valley/plugins/__init__.py](cases/sa_valley/plugins/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 36. [cases/sa_valley/problem/__init__.py](cases/sa_valley/problem/__init__.py)

源文件 SHA256：`c96177f222de97ad3c866faa1cda30ef620890cc2ccc2dcae7c25f928df4106c`；5 行。

````python
from .valley import ValleyProblem


def build_problem():
    return ValleyProblem()
````

## 37. [cases/sa_valley/problem/valley.py](cases/sa_valley/problem/valley.py)

源文件 SHA256：`0ff5c4a9868fa4ecd841be03deab3c74d6ff19e8d4525276a1188bce0f213c19`；20 行。

````python
"""SA 求解各向异性二次谷地，最优点 [-1.5, 0.75]。"""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class ValleyProblem(BlackBoxProblem):
    optimum = (-1.5, 0.75)

    def __init__(self):
        super().__init__(name="SA 二维谷地", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] + 1.5) ** 2 + 4.0 * (x[1] - 0.75) ** 2)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
````

## 38. [cases/sa_valley/run_solver.py](cases/sa_valley/run_solver.py)

源文件 SHA256：`ab283d8f4ae5229c5ed6e690ffba71ddfd54587d9d880bbb49da3558ccc24db9`；17 行。

````python
"""
CLI entry point for running the solver.

Usage:
    python run_solver.py
    python run_solver.py --check
"""

from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
````

## 39. [cases/sa_valley/run_trainer.py](cases/sa_valley/run_trainer.py)

源文件 SHA256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`；4 行。

````python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
````

## 40. [cases/sa_valley/runtime/__init__.py](cases/sa_valley/runtime/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 41. [cases/sa_valley/solver/__init__.py](cases/sa_valley/solver/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 42. [project_config.py](project_config.py)

源文件 SHA256：`f9893a745cb2e6413b904359807f8b0dd3e6a752aa312881f5c9e3b007377cc1`；18 行。

````python
"""两个独立 Case 的并发属于 Project，唯一 L0 在此授权。"""
L0 = {
    "namespace": "assembled_parallel_cases",
    "offer": {"threads": 2, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 2, "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{
    "name": "independent_searches", "cases": ["de_bowl", "sa_valley"],
    "policy": "parallel", "max_workers": 2,
    "case_modes": {"de_bowl": "build", "sa_valley": "build"},
    "resource_requests": {
        "de_bowl": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
        "sa_valley": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    },
}]
GROUPS = {"default": {"stages": ["independent_searches"]}}
````

## 43. [run_and_report.py](run_and_report.py)

源文件 SHA256：`5cbef9320af57fd1ed0c4b08ddf85d37d48b047f3c15fa817cbb903ace11c462`；149 行。

````python
"""正式 Project 执行 + 只读结果对账；不实现第二套求解/并发循环。"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.de_bowl.config import MAX_STEPS as DE_STEPS, POPULATION_SIZE, BATCH_SIZE
from cases.de_bowl.problem import build_problem as de_problem
from cases.sa_valley.config import MAX_STEPS as SA_STEPS
from cases.sa_valley.problem import build_problem as sa_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, payload):
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


def utc_timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds")


def summarize(project, wall_seconds):
    if project["exit_code"] or project["status"] != "ok":
        raise RuntimeError("Project failed; inspect results/project_result.json")
    cases = {case["request"]["case_name"]: case for case in project["cases"]}
    if set(cases) != {"de_bowl", "sa_valley"}:
        raise RuntimeError("Project must contain exactly the two assembled Cases")
    specifications = {"de_bowl": (de_problem, DE_STEPS, POPULATION_SIZE + (DE_STEPS - 1) * BATCH_SIZE),
                      "sa_valley": (sa_problem, SA_STEPS, SA_STEPS)}
    summaries = []
    for name, (problem_builder, expected_steps, expected_evaluations) in specifications.items():
        case = cases[name]
        if not case["ok"] or case["identity"]["project_run_id"] != project["run_id"]:
            raise RuntimeError(f"{name} did not successfully complete this Project run")
        output, resources = case["output"], case["resource_usage"]
        grant, context = resources["authorized_grant"], resources["effective_context"]
        if not resources["binding"]["current"] or grant["threads"] != 1 or grant["workers"] != 1:
            raise RuntimeError(f"{name} did not bind its one-thread/one-worker Project grant")
        if output["report"]["steps"] != expected_steps or output["report"]["evaluation_count"] != expected_evaluations:
            raise RuntimeError(f"{name} progress/evaluation count differs from its declared budget")
        candidate = output["best_solution"]["values"]
        # 报告阶段独立解析核对，不冒充持久 raw evidence，不加入求解求值计数。
        problem = problem_builder()
        raw_check = float(problem.evaluate(candidate))
        if not math.isfinite(raw_check) or not math.isclose(raw_check, output["best_objectives"][0], rel_tol=1e-12, abs_tol=1e-14):
            raise RuntimeError(f"{name} final objective disagrees with the analytical check")
        if len(candidate) != 2 or not all(-4.0 <= value <= 4.0 for value in candidate):
            raise RuntimeError(f"{name} final candidate violates the declared bounds")
        if not case["finished_at"] > case["started_at"] > 0:
            raise RuntimeError(f"{name} has no valid formal lifecycle timestamps")
        summaries.append({
            "case": name, "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
            "adapter": case["metadata"]["runtime_state"]["adapter"],
            "best_candidate": candidate, "best_candidate_token": output["best_candidate_token"],
            "best_objectives": output["best_objectives"], "raw_objective_recomputed": raw_check,
            "known_optimum": list(problem.optimum), "known_optimal_objective": 0.0,
            "distance_to_known_optimum": math.dist(candidate, problem.optimum),
            "logical_steps": output["report"]["steps"], "evaluations": output["report"]["evaluation_count"],
            "started_at": case["started_at"], "finished_at": case["finished_at"],
            "started_utc": utc_timestamp(case["started_at"]), "finished_utc": utc_timestamp(case["finished_at"]),
            "elapsed_seconds": case["elapsed_seconds"], "solver_elapsed_seconds": output["report"]["elapsed_sec"],
            "authorized_grant": grant, "namespace": context["namespace"],
            "lease_id": context["lease"]["lease_id"], "resource_binding_current": resources["binding"]["current"],
        })
    if len({row["namespace"] for row in summaries}) != 2 or len({row["lease_id"] for row in summaries}) != 2:
        raise RuntimeError("Cases must have distinct Project namespaces and resource leases")
    overlap_start = max(row["started_at"] for row in summaries)
    overlap_end = min(row["finished_at"] for row in summaries)
    overlap = max(0.0, overlap_end - overlap_start)
    if overlap <= 0:
        raise RuntimeError("No observed lifecycle overlap; do not claim this run demonstrated concurrent Cases")
    return {
        "project_run_id": project["run_id"], "status": project["status"], "wall_seconds": wall_seconds,
        "stage_policy": "parallel", "stage_max_workers": 2, "cases": summaries,
        "lifecycle_overlap_seconds": overlap, "overlap_started_utc": utc_timestamp(overlap_start),
        "overlap_finished_utc": utc_timestamp(overlap_end),
        "overlap_note": "Formal Case lifecycle intervals overlap; this is not a CPU utilization or speedup benchmark.",
        "checks": ["两个独立 Case 均通过正式 Project 执行", "两段 Case 生命周期发生真实重叠",
                   "每个 Case 的 threads=1、workers=1 且 binding.current=true", "Case 运行身份、资源 lease 与 namespace 彼此独立",
                   "求值次数与各算法声明预算一致", "最终候选、原始函数解析核对和问题边界一致"],
    }


def write_report(summary):
    lines = ["# 两个独立 Case 的实际并发结果", "",
             f"Project run：`{summary['project_run_id']}`。", "",
             f"- Stage：`parallel`，`max_workers=2`。",
             f"- 实际观察到的 Case 生命周期重叠：`{summary['lifecycle_overlap_seconds']:.6f}` 秒。",
             f"- 重叠区间：`{summary['overlap_started_utc']}` → `{summary['overlap_finished_utc']}`。",
             f"- 整体入口耗时：`{summary['wall_seconds']:.6f}` 秒。", "",
             "重叠使用正式 CaseRunResult 的 started_at/finished_at 计算，包含构建、运行、清理和发布；",
             "它证明两个 Case 生命周期并发，不证明某一瞬间两个目标函数都占用 CPU，也不是加速比测试。", ""]
    for case in summary["cases"]:
        lines += [f"## {case['case']} · {case['adapter']}", "",
                  f"- 最终候选：`{case['best_candidate']}`。",
                  f"- 目标：`{case['best_objectives'][0]:.12g}`；已知最优值 `0`，最优点 `{case['known_optimum']}`。",
                  f"- `{case['logical_steps']}` 次逻辑提交、`{case['evaluations']}` 次求值。",
                  f"- 开始：`{case['started_utc']}`；结束：`{case['finished_utc']}`。",
                  f"- Case 生命周期耗时 `{case['elapsed_seconds']:.6f}` 秒；Solver 报告耗时 `{case['solver_elapsed_seconds']:.6f}` 秒。",
                  f"- L0 授权：threads=`{case['authorized_grant']['threads']}`、workers=`{case['authorized_grant']['workers']}`。",
                  f"- namespace：`{case['namespace']}`。", f"- lease：`{case['lease_id']}`。", ""]
    lines += ["## 对账", ""] + [f"- {item}。" for item in summary["checks"]]
    lines += ["", "解析重算仅用于报告核对；没有 Bias，所以本例选择目标与原始目标一致。",
              "DE 与 SA 使用不同问题、不同 Solver、不同解池，没有交换候选，也没有共享 Unit。",
              "该结果不能用于比较 DE 与 SA 优劣：问题、步数、批量数都不同。", "",
              "完整正式返回值：[project_result.json](results/project_result.json)；简明汇总：[summary.json](results/summary.json)。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="只重新核对已保存结果，不重新求解")
    args = parser.parse_args()
    if args.report_only:
        project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
        timing = json.loads((RESULTS / "timing.json").read_text(encoding="utf-8"))
        if timing["project_run_id"] != project["run_id"]:
            raise RuntimeError("saved wall timing belongs to a different Project run")
        wall_seconds = timing["wall_seconds"]
    else:
        started = time.perf_counter()
        project = execute_project(ROOT).as_dict()
        wall_seconds = time.perf_counter() - started
        write_json(RESULTS / "project_result.json", project)
        write_json(RESULTS / "timing.json", {"project_run_id": project["run_id"], "wall_seconds": wall_seconds})
    summary = summarize(project, wall_seconds)
    write_json(RESULTS / "summary.json", summary)
    for case in summary["cases"]:
        write_json(RESULTS / "cases" / (case["case"] + ".json"), case)
    write_report(summary)
    print(json.dumps({"project_run_id": summary["project_run_id"], "overlap_seconds": summary["lifecycle_overlap_seconds"],
                      "cases": [{key: row[key] for key in ("case", "logical_steps", "evaluations", "best_candidate", "best_objectives", "namespace")}
                                for row in summary["cases"]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## 44. [run_project.py](run_project.py)

源文件 SHA256：`7bda03a21a381307647fdac0e4da4f1bd28ba84ac81b31d1f143dd2ef0004b68`；12 行。

````python
"""Run this project through the shared blackbase Project substrate."""

from pathlib import Path

from _bootstrap import bootstrap


if __name__ == "__main__":
    bootstrap()
    from nsgablack.project.project_runner import main

    raise SystemExit(main(Path(__file__).resolve().parent))
````
