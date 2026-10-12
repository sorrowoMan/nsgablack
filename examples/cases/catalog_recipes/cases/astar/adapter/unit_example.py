"""算法决定提案；算法管线构建候选 Unit。复制后实现自己的 update 策略。"""
from nsgablack.adapters import CandidateProposerAdapter


class UnitExampleAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Builds candidate Units through the configured pipeline without owning context keys."

    def __init__(self, count=4, *, unit_binding=None):
        super().__init__(name="unit_example", unit_binding=unit_binding)
        self.count = int(count)

    def propose(self, control, context):
        return self.build_candidate_units(
            [control.init_candidate(context) for _ in range(self.count)], context)

    def update(self, control, candidates, feedback, context):
        # feedback 为 OptimizationFeedbackBatch；可按需消费 objectives/violations。
        pass
