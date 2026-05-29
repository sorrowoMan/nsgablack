"""
Main entry point for running the project.

This script reads the project_config.py, discovers and loads the cases,
and then uses nsgablack's orchestration capabilities to run them.
"""
import argparse
import importlib
from pathlib import Path

from nsgablack.core import SerialStageSolver
from nsgablack.core.state import SnapshotStore, InMemorySnapshotStore

def run_project(group_name: str = "default"):
    """
    Runs the project based on the specified group.
    """
    print(f"Running project group: {group_name}")

    # In a real implementation, this would use a proper orchestration engine.
    # For this demo, we'll use a simplified version with SerialStageSolver.

    # 1. Load project config
    try:
        from project_config import GROUPS, STAGES
    except ImportError:
        print("Error: Could not import GROUPS and STAGES from project_config.py")
        return

    # 2. Initialize a shared snapshot store for artifact passing
    snapshot_store = InMemorySnapshotStore()

    # 3. Build the stages for the selected group
    group = GROUPS.get(group_name)
    if not group:
        print(f"Error: Group '{group_name}' not found in project_config.py")
        return

    project_stages = []
    for stage_name in group["stages"]:
        stage_config = next((s for s in STAGES if s["name"] == stage_name), None)
        if not stage_config:
            print(f"Warning: Stage '{stage_name}' not found in STAGES config.")
            continue

        # In a real scenario, you'd have a parallel runner here.
        # For simplicity, we'll just run cases sequentially within the stage.
        for case_name in stage_config["cases"]:
            print(f"  Preparing case: {case_name} for stage: {stage_name}")
            try:
                # Dynamically import the build_solver function from the case
                module_path = f"cases.{case_name}.build_solver"
                case_module = importlib.import_module(module_path)
                build_solver_func = getattr(case_module, "build_solver")

                # Here you would handle artifact injection based on stage_config["dependencies"]
                # For demo, we just build the solver.
                solver = build_solver_func()
                solver.set_snapshot_store(snapshot_store)
                
                # A real implementation would wrap this in a stage runner
                print(f"    Running solver for {case_name}...")
                # solver.solve() # This would run the actual optimization

            except (ImportError, AttributeError) as e:
                print(f"    Error loading case '{case_name}': {e}")

    print("Project run finished (simulation).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a multi-case project.")
    parser.add_argument(
        "--group",
        type=str,
        default="default",
        help="The name of the execution group to run from project_config.py",
    )
    args = parser.parse_args()
    run_project(args.group)
