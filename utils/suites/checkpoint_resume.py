"""
Authority suite: checkpoint + resume.

Attaches CheckpointResumePlugin for crash recovery and run continuation.
"""

from __future__ import annotations

from ...plugins import CheckpointResumeConfig, CheckpointResumePlugin


def attach_checkpoint_resume(
    solver,
    *,
    checkpoint_dir: str = "runs/checkpoints",
    file_prefix: str = "checkpoint",
    save_every: int = 10,
    keep_last: int = 5,
    auto_resume: bool = False,
    resume_from: str = "latest",
    save_on_finish: bool = True,
    restore_plugin_state: bool = True,
    restore_rng_state: bool = True,
    strict: bool = False,
):
    if not hasattr(solver, "add_plugin"):
        raise ValueError("attach_checkpoint_resume: solver missing add_plugin()")

    cfg = CheckpointResumeConfig(
        checkpoint_dir=str(checkpoint_dir),
        file_prefix=str(file_prefix),
        save_every=int(save_every),
        keep_last=int(keep_last),
        auto_resume=bool(auto_resume),
        resume_from=str(resume_from),
        save_on_finish=bool(save_on_finish),
        restore_plugin_state=bool(restore_plugin_state),
        restore_rng_state=bool(restore_rng_state),
        strict=bool(strict),
    )
    plugin = CheckpointResumePlugin(config=cfg)

    if getattr(solver, "get_plugin", None) is not None and solver.get_plugin(plugin.name) is not None:
        return solver.get_plugin(plugin.name)

    solver.add_plugin(plugin)
    return plugin

