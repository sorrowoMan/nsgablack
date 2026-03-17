"""Dynamic CLI signal provider demo."""

import time

try:
    from nsgablack.utils.dynamic.cli_provider import CLISignalProvider
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.utils.dynamic.cli_provider import CLISignalProvider


def main():
    provider = CLISignalProvider()
    print("Type signals like: weather=bad risk=0.8 or JSON {\"weather\": \"good\"}")
    print("Reading for 5 seconds...")
    for _ in range(5):
        time.sleep(1)
        print("latest:", provider.read())


if __name__ == "__main__":
    main()
