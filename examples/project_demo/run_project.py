"""Thin entrypoint for the shared Project/Case/L0 runtime."""

from pathlib import Path

from nsgablack.project.project_runner import main


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
