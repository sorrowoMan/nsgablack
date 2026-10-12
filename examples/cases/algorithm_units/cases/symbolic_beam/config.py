"""兼容旧示例参数，并作为标准 Case 的配置入口。"""
import argparse

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Standalone symbolic demo: joint bundle + beam search",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--n-train", type=int, default=256)
    p.add_argument("--n-valid", type=int, default=128)
    p.add_argument("--n-candidates", type=int, default=192)
    p.add_argument("--true-terms", type=int, default=6)
    p.add_argument("--noise", type=float, default=0.05)
    p.add_argument("--max-terms", type=int, default=8)
    p.add_argument("--ridge-alpha", type=float, default=1e-3)
    p.add_argument("--generations", type=int, default=25)
    p.add_argument("--beam-width", type=int, default=16)
    p.add_argument("--shortlist-size", type=int, default=64)
    p.add_argument("--expansions-per-state", type=int, default=6)
    p.add_argument("--bundle-size", type=int, default=3)
    p.add_argument("--max-candidates", type=int, default=320)
    p.add_argument("--flip-prob", type=float, default=0.04)
    p.add_argument("--objective1-weight", type=float, default=0.02)
    p.add_argument("--report-interval", type=int, default=5)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--show-top", type=int, default=10)
    p.add_argument("--progress", action="store_true")
    p.add_argument("--csv", type=str, default="")
    p.add_argument("--target-col", type=str, default="ci")
    p.add_argument("--fold-col", type=str, default="test_fold_1")
    p.add_argument("--max-pairwise", type=int, default=64)
    return p

