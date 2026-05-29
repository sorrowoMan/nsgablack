#!/usr/bin/env python
"""Development shim — delegates to the canonical CLI in nsgablack/nsgablack/__main__.py."""

from nsgablack.nsgablack.__main__ import (  # noqa: F401
    build_parser,
    main,
    _format_doctor_problem_lines,
)


if __name__ == "__main__":
    raise SystemExit(main())
