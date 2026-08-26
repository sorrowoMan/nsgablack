"""Canonical baseline Trainer CLI."""

from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="mlblack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
