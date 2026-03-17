"""Context schema demo: build a minimal evaluation context."""

try:
    from nsgablack.core.state.context_schema import build_minimal_context
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.state.context_schema import build_minimal_context


def main():
    ctx = build_minimal_context(
        generation=5,
        individual_id=1,
        constraints=[0.0, 0.2],
        constraint_violation=0.2,
        seed=42,
        metadata={"source": "context_schema_demo"},
        extra={"note": "hello"},
    )
    print("context:", ctx)


if __name__ == "__main__":
    main()
