"""Use the canonical Project CLI for assembly checks and actual execution."""
from pathlib import Path
from nsgablack.project.project_runner import main


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
