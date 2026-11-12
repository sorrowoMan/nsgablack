"""Thin CLI assembly over the existing signed checkpoint lifecycle."""
from pathlib import Path

from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin


def attach_production_checkpoint(solver, args):
    directory = getattr(args, "checkpoint_dir", None)
    resume = getattr(args, "resume", None)
    key_file = getattr(args, "checkpoint_key_file", None)
    specified_interval = getattr(args, "checkpoint_every", None)
    interval = 10 if specified_interval is None else int(specified_interval)
    if interval < 1:
        raise ValueError("--checkpoint-every must be positive")
    if not directory and resume and resume != "latest":
        directory = str(Path(resume).expanduser().resolve().parent)
    if not directory:
        if resume or key_file or specified_interval is not None:
            raise ValueError("checkpoint options require --checkpoint-dir or an explicit --resume PATH")
        return None
    directory = Path(directory).expanduser().resolve()
    if resume and resume != "latest":
        resume = str(Path(resume).expanduser().resolve())
    key_path = Path(key_file).expanduser().resolve() if key_file else directory / "signing.checkpoint-key"
    # No filesystem writes here: Doctor/build-check must remain read-only.
    plugin = CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(directory), file_prefix="production", save_every=interval,
        save_on_finish=True, auto_resume=bool(resume), resume_from=resume or "latest",
        strict=True, hmac_key_file=str(key_path), create_key_file=not bool(resume),
        mirror_final_to_directory=True,
        trusted_roots=(str(directory),),
    ))
    solver.add_plugin(plugin)
    print(f"[checkpoint] directory={directory} every={interval} resume={resume or 'fresh'}")
    return plugin
