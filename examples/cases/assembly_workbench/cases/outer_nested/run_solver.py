"""独立执行也委托正式 Project L0，不自行构造授权。"""
import sys
from pathlib import Path
from blackbase.project import run_standard_case_cli

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--check" in args:
        return run_standard_case_cli(__file__, framework="nsgablack", argv=args)
    from nsgablack.project.project_runner import main as project_main
    return project_main(project_root=Path(__file__).resolve().parents[2],
                        argv=["--group", "nested", *args])

if __name__ == "__main__":
    raise SystemExit(main())
