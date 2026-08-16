# -*- coding: utf-8 -*-
"""Case package import surface."""

from __future__ import annotations

import sys
from pathlib import Path

_CASE_ROOT = Path(__file__).resolve().parent
if str(_CASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASE_ROOT))

