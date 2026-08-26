"""Algorithm strategy for the baseline Solver."""

from nsgablack.adapters import VNSAdapter, VNSConfig


def build_adapter() -> VNSAdapter:
    return VNSAdapter(VNSConfig(batch_size=2, k_max=1, base_sigma=0.1))
