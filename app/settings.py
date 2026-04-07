from __future__ import annotations

from PySide6.QtCore import QSettings


class Settings:
    """Thin wrapper around QSettings for app preferences."""

    def __init__(self) -> None:
        self._settings = QSettings("DevScratchpad", "DevScratchpad")

    def value(self, key: str, default=None):
        return self._settings.value(key, default)

    def bool(self, key: str, default: bool = False) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._settings.value(key, default))
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    @property
    def theme(self) -> str:
        return str(self.value("theme", "dark"))

    @property
    def font_family(self) -> str:
        return str(self.value("font_family", "Menlo"))

    @property
    def font_size(self) -> int:
        return self.int("font_size", 13)

    @property
    def tab_width(self) -> int:
        return self.int("tab_width", 4)

    @property
    def wrap_lines(self) -> bool:
        return self.bool("wrap_lines", True)

