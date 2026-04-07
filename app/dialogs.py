from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import LANGUAGES


class FindReplaceBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.next_button = QPushButton("Next")
        self.prev_button = QPushButton("Previous")
        self.replace_button = QPushButton("Replace")
        self.replace_all_button = QPushButton("Replace All")
        self.close_button = QPushButton("Close")
        for widget in (
            QLabel("Find"),
            self.find_input,
            self.replace_input,
            self.prev_button,
            self.next_button,
            self.replace_button,
            self.replace_all_button,
            self.close_button,
        ):
            layout.addWidget(widget)
        self.setVisible(False)


class RenameDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Note")
        layout = QFormLayout(self)
        self.title_input = QLineEdit(title)
        layout.addRow("Title", self.title_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def title(self) -> str:
        return self.title_input.text().strip() or "Untitled"


class GoToLineDialog(QDialog):
    def __init__(self, max_line: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Go to Line")
        layout = QFormLayout(self)
        self.line_input = QSpinBox()
        self.line_input.setRange(1, max(1, max_line))
        layout.addRow("Line", self.line_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def line(self) -> int:
        return self.line_input.value()


class CommandPalette(QDialog):
    def __init__(self, commands: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command")
        self.list_widget = QListWidget()
        layout.addWidget(self.search)
        layout.addWidget(self.list_widget)
        self.commands = commands
        self._populate(commands)
        self.search.textChanged.connect(self._filter)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())

    def _populate(self, commands: list[str]) -> None:
        self.list_widget.clear()
        for command in commands:
            self.list_widget.addItem(QListWidgetItem(command))
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _filter(self, text: str) -> None:
        needle = text.lower()
        self._populate([command for command in self.commands if needle in command.lower()])

    def selected_command(self) -> str | None:
        item = self.list_widget.currentItem()
        return item.text() if item else None


class SearchFilters(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search notes")
        self.language = QComboBox()
        self.language.addItems(["All", *LANGUAGES])
        self.pinned = QCheckBox("Pinned")
        self.favorite = QCheckBox("Favorites")
        layout.addWidget(self.query)
        layout.addWidget(self.language)
        layout.addWidget(self.pinned)
        layout.addWidget(self.favorite)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
