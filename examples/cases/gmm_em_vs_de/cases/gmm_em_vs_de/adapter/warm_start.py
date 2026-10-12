"""在阶段首次提案时读取上一阶段结果，经 VNS builder 构建当前 Unit。"""
from nsgablack.adapters import VNSAdapter


class WarmStartVNSAdapter(VNSAdapter):
    def propose(self, control, context):
        if self.current_unit is None:
            best = getattr(control, "best_x", None)
            if best is not None:
                self.current_x = best
                self.current_score = None
        return super().propose(control, context)
