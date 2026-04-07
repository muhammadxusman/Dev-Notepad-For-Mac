from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCursor, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .syntax import SyntaxHighlighter


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    cursorInfoChanged = Signal(int, int, int, int, int)

    def __init__(self, language: str = "Plain Text", parent=None) -> None:
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = SyntaxHighlighter(self.document(), language)
        self._tab_width = 4
        self.line_number_bg = QColor("#161b22")
        self.line_number_fg = QColor("#6e7681")
        self.current_line_bg = QColor("#1f2937")
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setFont(QFont("Menlo", 13))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setUndoRedoEnabled(True)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.cursorPositionChanged.connect(self.emit_cursor_info)
        self.textChanged.connect(self.emit_cursor_info)
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def set_editor_font(self, family: str, size: int) -> None:
        font = QFont(family, size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.update_tab_width(self._tab_width)

    def update_tab_width(self, width: int) -> None:
        self._tab_width = width
        metrics = self.fontMetrics()
        self.setTabStopDistance(metrics.horizontalAdvance(" ") * width)

    def set_language(self, language: str) -> None:
        self.highlighter.set_language(language)

    def set_editor_theme(self, dark: bool) -> None:
        if dark:
            self.line_number_bg = QColor("#161b22")
            self.line_number_fg = QColor("#6e7681")
            self.current_line_bg = QColor("#1f2937")
        else:
            self.line_number_bg = QColor("#f6f8fa")
            self.line_number_fg = QColor("#57606a")
            self.current_line_bg = QColor("#eef6ff")
        self.line_number_area.update()
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_bg)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.line_number_fg)
                painter.drawText(0, top, self.line_number_area.width() - 6, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self) -> None:
        selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_bg)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def emit_cursor_info(self) -> None:
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        text = self.toPlainText()
        selected = len(cursor.selectedText())
        self.cursorInfoChanged.emit(line, col, self.blockCount(), len(text), selected)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            block_text = cursor.block().text()
            indent = block_text[: len(block_text) - len(block_text.lstrip(" \t"))]
            super().keyPressEvent(event)
            if block_text.rstrip().endswith(("{", "[", "(", ":")):
                indent += " " * self._tab_width
            self.insertPlainText(indent)
            return
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selection()
            else:
                self.insertPlainText(" " * self._tab_width)
            return
        if event.key() == Qt.Key.Key_Backtab:
            self._outdent_selection()
            return
        super().keyPressEvent(event)

    def _indent_selection(self) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            cursor.setPosition(block.position())
            cursor.insertText(" " * self._tab_width)
        cursor.endEditBlock()

    def _outdent_selection(self) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            text = block.text()
            remove = min(len(text) - len(text.lstrip(" ")), self._tab_width)
            if remove:
                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, remove)
                cursor.removeSelectedText()
        cursor.endEditBlock()
