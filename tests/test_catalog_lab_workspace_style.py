"""Theme text remains readable and a browser value cannot inject CSS."""
from __future__ import annotations

import pytest

from nsgablack.catalog.lab_workspace_style import PALETTES, workspace_styles


def _luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
              for v in channels]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


@pytest.mark.parametrize("theme", ("dark", "light"))
def test_theme_text_and_actions_meet_normal_text_contrast(theme):
    colors = PALETTES[theme]
    for surface in ("background", "surface", "raised", "sidebar", "editor", "code"):
        for text in ("ink", "muted"):
            assert _contrast(colors[text], colors[surface]) >= 4.5, (theme, text, surface)
    assert _contrast(colors["on_accent"], colors["accent_fill"]) >= 4.5
    for text, surface in (("accent", "accent_soft"), ("error", "error_soft"),
                          ("warning", "warning_soft"), ("success", "success_soft")):
        assert _contrast(colors[text], colors[surface]) >= 4.5, (theme, text)


@pytest.mark.parametrize("value", (None, "", "DARK", "<style>body{display:none}</style>", {}, []))
def test_invalid_appearance_is_rejected(value):
    with pytest.raises(ValueError, match="workspace_theme_invalid"):
        workspace_styles(value)


def test_system_theme_contains_both_native_color_schemes():
    styles = workspace_styles("system")
    assert "color-scheme:light" in styles
    assert "prefers-color-scheme:dark" in styles
    assert "color-scheme:dark" in styles
    assert PALETTES["light"]["background"] in styles
    assert PALETTES["dark"]["background"] in styles
