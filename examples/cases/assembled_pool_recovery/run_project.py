"""Run this project through the shared blackbase Project substrate."""

from pathlib import Path

from _bootstrap import bootstrap


if __name__ == "__main__":
    bootstrap()
    from nsgablack.project.project_runner import main

    raise SystemExit(main(Path(__file__).resolve().parent))
