"""标准 Project CLI；--group 切换装配场景，--check --build-check 检查真实构建。"""
from pathlib import Path
from nsgablack.project.project_runner import main


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
