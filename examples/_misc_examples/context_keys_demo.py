"""Context keys demo: show canonical keys used across components."""

try:
    from nsgablack.core.state.context_keys import (
        KEY_GENERATION,
        KEY_INDIVIDUAL_ID,
        KEY_CONSTRAINTS,
        KEY_CONSTRAINT_VIOLATION,
        KEY_ROLE,
    )
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.state.context_keys import (
        KEY_GENERATION,
        KEY_INDIVIDUAL_ID,
        KEY_CONSTRAINTS,
        KEY_CONSTRAINT_VIOLATION,
        KEY_ROLE,
    )


def main():
    context = {
        KEY_GENERATION: 12,
        KEY_INDIVIDUAL_ID: 3,
        KEY_CONSTRAINTS: [0.0, 0.1],
        KEY_CONSTRAINT_VIOLATION: 0.1,
        KEY_ROLE: "explorer",
    }
    print("context:", context)


if __name__ == "__main__":
    main()
