"""Colours shared by the PNG charts and the interactive ones.

Categorical series colours are assigned in this fixed order (one per faction); the light and dark sets were
validated against their own surface. The sequential ramp is one hue, listed from the lowest to the highest value:
dark on the light theme for large values, and light on the dark theme.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    ink: str
    ink_secondary: str
    ink_muted: str
    grid: str
    axis: str
    series: tuple
    sequential: tuple


LIGHT = Theme(
    name="light", surface="#fcfcfb", ink="#0b0b0b", ink_secondary="#52514e", ink_muted="#898781",
    grid="#e1e0d9", axis="#c3c2b7",
    series=("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"),
    sequential=("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"),
)

DARK = Theme(
    name="dark", surface="#1a1a19", ink="#ffffff", ink_secondary="#c3c2b7", ink_muted="#898781",
    grid="#2c2c2a", axis="#383835",
    series=("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
    sequential=("#0d366b", "#104281", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"),
)

THEMES = {"light": LIGHT, "dark": DARK}
