"""Logging helper demo: JSON vs plain logging."""

try:
    from nsgablack.utils.engineering.logging_config import configure_logging
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.utils.engineering.logging_config import configure_logging

import logging


def main():
    configure_logging(level="INFO", json_format=False, force=True)
    logging.getLogger("demo").info("plain log message")

    configure_logging(level="INFO", json_format=True, force=True)
    logging.getLogger("demo").info("json log message")


if __name__ == "__main__":
    main()
