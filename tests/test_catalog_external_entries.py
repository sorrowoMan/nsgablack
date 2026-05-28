from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Catalog is now DB-backed; TOML external entry loading tests need rewriting for DB-based catalog.")
