"""问题管线的规范装配入口，显式保存本例有状态叶组件。"""
from nsgablack.representation import ContextGaussianMutation, RepresentationPipeline, UniformInitializer

from .repair import RecipeRepair


class RecipePipeline(RepresentationPipeline):
    """为本 Case 实际使用的三个有状态组件显式提供 checkpoint codec。"""
    state_recovery_level = "L1"
    state_recovery_notes = "Restores initializer/mutator RNG and repair observation counters."

    def get_state(self):
        return {"schema": "assembly_workbench.recipe_pipeline/v1",
                "initializer": self.initializer.get_state(),
                "mutator": self.mutator.get_state(), "repair": self.problem_repair.get_state()}

    def set_state(self, state):
        if (set(state) != {"schema", "initializer", "mutator", "repair"}
                or state["schema"] != "assembly_workbench.recipe_pipeline/v1"):
            raise ValueError("incompatible recipe pipeline state")
        self.initializer.set_state(state["initializer"])
        self.mutator.set_state(state["mutator"])
        self.problem_repair.set_state(state["repair"])


def build_pipeline(sigma):
    # 初始值有意覆盖边界外区域，让运行结果能验证 repair 确实工作。
    repair = RecipeRepair()
    return RecipePipeline(initializer=UniformInitializer(-0.2, 1.2),
        mutator=ContextGaussianMutation(base_sigma=sigma), repair=repair), repair
