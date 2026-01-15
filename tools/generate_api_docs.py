"""Generate Sphinx API docs with sphinx-apidoc."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    docs_api_dir = os.path.join(root_dir, "docs", "api")

    os.makedirs(docs_api_dir, exist_ok=True)

    exclude = [
        os.path.join(root_dir, "docs"),
        os.path.join(root_dir, "test"),
        os.path.join(root_dir, "examples"),
        os.path.join(root_dir, "scripts"),
        os.path.join(root_dir, "data"),
        os.path.join(root_dir, "reports"),
        os.path.join(root_dir, "build"),
        os.path.join(root_dir, "dist"),
    ]

    cmd = [
        sys.executable,
        "-m",
        "sphinx.ext.apidoc",
        "-f",
        "-o",
        docs_api_dir,
        root_dir,
        *exclude,
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
