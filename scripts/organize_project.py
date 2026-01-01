#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Structure Organization Script
Cleans and organizes the nsgablack project structure
"""

import os
import shutil
from pathlib import Path

# Project root directory
ROOT = Path(__file__).parent.parent


def create_directories():
    """Create required directory structure"""
    dirs = [
        "examples/demos",
        "examples/tutorials",
        "data/results",
        "data/experiments",
        "data/visualizations",
        "docs/api",
        "docs/tutorials",
        "scripts",
    ]

    for dir_path in dirs:
        (ROOT / dir_path).mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created directory: {dir_path}")


def move_demo_files():
    """Move demo scripts to examples/demos/"""
    demo_files = [
        "bias_system_demo.py",
        "demo_tsp.py",
        "demo_using_my_classes.py",
        "final_bias_demo.py",
        "real_bias_demo.py",
    ]

    target_dir = ROOT / "examples" / "demos"

    for file in demo_files:
        src = ROOT / file
        if src.exists():
            dst = target_dir / file
            shutil.move(str(src), str(dst))
            print(f"[MOVE] {file} -> examples/demos/")


def move_test_files():
    """Move test scripts to test/"""
    test_files = [
        "test_advisor_integration.py",
        "test_advisor_role.py",
        "test_advisor_simple.py",
        "test_enhanced_search.py",
    ]

    target_dir = ROOT / "test"

    for file in test_files:
        src = ROOT / file
        if src.exists():
            dst = target_dir / file
            shutil.move(str(src), str(dst))
            print(f"[TEST] {file} -> test/")


def move_result_files():
    """Move history and image files to data/results/"""
    # Move JSON history files
    json_files = list(ROOT.glob("*_history.json"))
    target_dir = ROOT / "data" / "results"

    for file in json_files:
        if "blackbox" in file.name or "intelligent" in file.name:
            dst = target_dir / file.name
            shutil.move(str(file), str(dst))
            print(f"[DATA] {file.name} -> data/results/")

    # Move image files
    png_files = list(ROOT.glob("*.png"))
    for file in png_files:
        dst = target_dir / file.name
        shutil.move(str(file), str(dst))
        print(f"[IMG] {file.name} -> data/results/")


def clean_examples_dir():
    """Clean non-example files from examples directory"""
    examples_dir = ROOT / "examples"
    target_dir = ROOT / "data" / "results"

    # Move JSON files from examples
    json_files = list(examples_dir.glob("*_history.json"))
    for file in json_files:
        dst = target_dir / file.name
        shutil.move(str(file), str(dst))
        print(f"[CLEAN] {file.name} -> data/results/")


def remove_temp_files():
    """Remove temporary files"""
    temp_files = [
        ROOT / "kk",
        ROOT / "CURRENT_STATUS_REPORT.md",  # If temporary
    ]

    for file in temp_files:
        if file.exists():
            file.unlink()
            print(f"[DELETE] {file.name}")


def update_gitignore():
    """Update .gitignore file"""
    gitignore_path = ROOT / ".gitignore"

    additions = """
# Project organization
data/results/
data/experiments/
data/visualizations/
*.history.json
*.png
!docs/**/*.png

# IDE
.idea/
*.swp
*.swo
"""

    with open(gitignore_path, "a", encoding="utf-8") as f:
        f.write(additions)

    print("[OK] Updated .gitignore")


def create_readme_for_dirs():
    """Create README files for directories"""
    readmes = {
        "data/results": "# Experiment Results\n\nThis directory contains optimization history and visualization results.",
        "examples/demos": "# Demo Scripts\n\nThis directory contains various feature demonstration scripts.",
        "examples/tutorials": "# Tutorials\n\nThis directory contains step-by-step tutorials.",
    }

    for dir_path, content in readmes.items():
        readme_file = ROOT / dir_path / "README.md"
        if not readme_file.exists():
            with open(readme_file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[README] Created {dir_path}/README.md")


def main():
    """Execute all organization tasks"""
    print("=" * 60)
    print("nsgablack Project Structure Organization")
    print("=" * 60)
    print()

    print("Step 1/8: Create directory structure")
    create_directories()
    print()

    print("Step 2/8: Move demo scripts")
    move_demo_files()
    print()

    print("Step 3/8: Move test files")
    move_test_files()
    print()

    print("Step 4/8: Move result files")
    move_result_files()
    print()

    print("Step 5/8: Clean examples directory")
    clean_examples_dir()
    print()

    print("Step 6/8: Remove temporary files")
    remove_temp_files()
    print()

    print("Step 7/8: Update .gitignore")
    update_gitignore()
    print()

    print("Step 8/8: Create directory READMEs")
    create_readme_for_dirs()
    print()

    print("=" * 60)
    print("Project structure organization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Check that files are organized correctly")
    print("2. Run tests to ensure everything works")
    print("3. Commit changes to git")
    print()


if __name__ == "__main__":
    main()
