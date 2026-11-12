"""从仓库中运行生成的标准 Project 入口。"""
import sys
from pathlib import Path


def bootstrap():
    root = Path(__file__).resolve().parent
    for path in (root, root.parents[2], root.parents[3]):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
