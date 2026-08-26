"""VNS strategy used by the innermost calibration Case."""

from nsgablack.adapters import VNSAdapter, VNSConfig


def build_adapter() -> VNSAdapter:
    return VNSAdapter(VNSConfig(batch_size=1, k_max=1, base_sigma=0.15))
