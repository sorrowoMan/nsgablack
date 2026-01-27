from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Failure:
    module: str
    error: str


def scan(package_name: str) -> tuple[list[str], list[Failure]]:
    pkg = importlib.import_module(package_name)
    modules = sorted([m.name for m in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + ".")])
    failures: list[Failure] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            failures.append(Failure(module=name, error=repr(exc)))
    return modules, failures


def main() -> int:
    # When executing from inside the repo folder, ensure the parent directory is on sys.path
    # so `import nsgablack` resolves correctly.
    repo_parent = Path(__file__).resolve().parents[2]
    if str(repo_parent) not in sys.path:
        sys.path.insert(0, str(repo_parent))

    targets = ["nsgablack.utils"]
    all_failures: list[Failure] = []
    total_modules = 0

    for target in targets:
        modules, failures = scan(target)
        total_modules += len(modules)
        all_failures.extend(failures)

    print(f"scanned_modules={total_modules}")
    print(f"failures={len(all_failures)}")
    for f in all_failures:
        print(f" - {f.module}: {f.error}")

    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
