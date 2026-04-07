from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .dialogs import CommandPalette, FindReplaceBar, GoToLineDialog, RenameDialog, SearchFilters
from .editor import CodeEditor
from .models import CATEGORIES, LANGUAGES, Note
from .settings import Settings
from .storage import NoteStore
from .text_utils import (
    TEMPLATES,
    dedupe_lines,
    detect_language,
    format_json,
    minify_json,
    sort_lines,
    spaces_to_tabs,
    tabs_to_spaces,
    trim_trailing_spaces,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.store = NoteStore()
        self.notes: dict[str, Note] = {}
        self.dirty: set[str] = set()
        self._loading = False
        self.setWindowTitle("Dev Scratchpad")
        self.resize(1180, 760)
        QApplication.instance().installEventFilter(self)

        self._build_ui()
        self._build_actions()
        self._build_menus()
        self._apply_theme(self.settings.theme)
        self._restore_session()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(3000)
        self.autosave_timer.timeout.connect(self.save_all)
        self.autosave_timer.start()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.toolbar = QToolBar("Quick Actions")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        splitter = QSplitter()
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.search_filters = SearchFilters()
        self.note_list = QListWidget()
        sidebar_layout.addWidget(self.search_filters)
        sidebar_layout.addWidget(self.note_list)
        splitter.addWidget(self.sidebar)

        editor_host = QWidget()
        editor_layout = QVBoxLayout(editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(8, 8, 8, 6)
        self.language_combo = QComboBox()
        self.language_combo.addItems(LANGUAGES)
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.copy_note_button = QPushButton("Copy Note")
        self.format_json_button = QPushButton("Format JSON")
        top_row.addWidget(QLabel("Language"))
        top_row.addWidget(self.language_combo)
        top_row.addWidget(QLabel("Category"))
        top_row.addWidget(self.category_combo)
        top_row.addStretch(1)
        top_row.addWidget(self.copy_note_button)
        top_row.addWidget(self.format_json_button)
        editor_layout.addLayout(top_row)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        editor_layout.addWidget(self.tabs)
        self.find_bar = FindReplaceBar()
        editor_layout.addWidget(self.find_bar)
        splitter.addWidget(editor_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 910])
        root.addWidget(splitter)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.cursor_label = QLabel("Ln 1, Col 1")
        self.count_label = QLabel("Lines 1 | Chars 0")
        self.lang_label = QLabel("Plain Text")
        self.save_label = QLabel("Saved")
        self.category_label = QLabel("Temp")
        self.status.addPermanentWidget(self.cursor_label)
        self.status.addPermanentWidget(self.count_label)
        self.status.addPermanentWidget(self.lang_label)
        self.status.addPermanentWidget(self.category_label)
        self.status.addPermanentWidget(self.save_label)

        self.tabs.currentChanged.connect(self._current_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.note_list.itemDoubleClicked.connect(self._open_note_from_item)
        self.search_filters.query.textChanged.connect(self.refresh_note_list)
        self.search_filters.language.currentTextChanged.connect(self.refresh_note_list)
        self.search_filters.pinned.stateChanged.connect(self.refresh_note_list)
        self.search_filters.favorite.stateChanged.connect(self.refresh_note_list)
        self.language_combo.currentTextChanged.connect(self._language_changed)
        self.category_combo.currentTextChanged.connect(self._category_changed)
        self.copy_note_button.clicked.connect(self.copy_entire_note)
        self.format_json_button.clicked.connect(self.format_json_action)
        self.find_bar.close_button.clicked.connect(lambda: self.find_bar.setVisible(False))
        self.find_bar.next_button.clicked.connect(lambda: self.find_next(False))
        self.find_bar.prev_button.clicked.connect(lambda: self.find_next(True))
        self.find_bar.replace_button.clicked.connect(self.replace_one)
        self.find_bar.replace_all_button.clicked.connect(self.replace_all)

    def _build_actions(self) -> None:
        self.new_note_action = QAction("New Note", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_note)
        self.save_action = QAction("Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_current)
        self.save_all_action = QAction("Save All", self, shortcut=QKeySequence("Ctrl+Meta+S"), triggered=self.save_all)
        self.rename_action = QAction("Rename Note", self, shortcut=QKeySequence("Meta+R"), triggered=self.rename_note)
        self.duplicate_action = QAction("Duplicate Note", self, shortcut=QKeySequence("Meta+D"), triggered=self.duplicate_note)
        self.pin_action = QAction("Pin Note", self, checkable=True, triggered=self.toggle_pin)
        self.favorite_action = QAction("Favorite Note", self, checkable=True, triggered=self.toggle_favorite)
        self.archive_action = QAction("Archive Note", self, triggered=self.archive_note)
        self.clear_action = QAction("Clear Note", self, triggered=self.clear_note)
        self.delete_action = QAction("Move to Trash", self, shortcut=QKeySequence.StandardKey.Delete, triggered=self.delete_note)
        self.open_file_action = QAction("Open File...", self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_file)
        self.save_file_action = QAction("Save to File", self, shortcut=QKeySequence("Meta+Shift+S"), triggered=self.save_to_file)
        self.export_action = QAction("Export Note...", self, triggered=self.export_note)
        self.find_action = QAction("Find/Replace", self, shortcut=QKeySequence.StandardKey.Find, triggered=self.show_find)
        self.go_to_line_action = QAction("Go to Line", self, shortcut=QKeySequence("Meta+L"), triggered=self.go_to_line)
        self.next_tab_action = QAction("Next Tab", self, shortcut=QKeySequence("Ctrl+Tab"), triggered=lambda: self._move_tab(1))
        self.prev_tab_action = QAction("Previous Tab", self, shortcut=QKeySequence("Ctrl+Shift+Tab"), triggered=lambda: self._move_tab(-1))
        self.toggle_sidebar_action = QAction("Toggle Sidebar", self, shortcut=QKeySequence("Meta+B"), triggered=self.toggle_sidebar)
        self.toggle_wrap_action = QAction("Toggle Line Wrap", self, shortcut=QKeySequence("Alt+Z"), triggered=self.toggle_wrap)
        self.palette_action = QAction("Command Palette", self, shortcut=QKeySequence("Meta+Shift+P"), triggered=self.open_palette)
        self.auto_detect_language_action = QAction("Auto Detect Language", self, triggered=self.auto_detect_language)
        self.copy_all_action = QAction("Copy Entire Note", self, triggered=self.copy_entire_note)
        self.copy_selection_action = QAction("Copy Selection", self, triggered=lambda: self.current_editor().copy() if self.current_editor() else None)
        self.format_json_act = QAction("Format JSON", self, triggered=self.format_json_action)
        self.minify_json_act = QAction("Minify JSON", self, triggered=self.minify_json_action)
        self.trim_spaces_action = QAction("Trim Trailing Spaces", self, triggered=lambda: self.transform_text(trim_trailing_spaces))
        self.tabs_to_spaces_action = QAction("Tabs to Spaces", self, triggered=lambda: self.transform_text(lambda t: tabs_to_spaces(t, self.settings.tab_width)))
        self.spaces_to_tabs_action = QAction("Spaces to Tabs", self, triggered=lambda: self.transform_text(lambda t: spaces_to_tabs(t, self.settings.tab_width)))
        self.uppercase_action = QAction("Uppercase", self, triggered=lambda: self.transform_text(str.upper))
        self.lowercase_action = QAction("Lowercase", self, triggered=lambda: self.transform_text(str.lower))
        self.sort_lines_action = QAction("Sort Lines", self, triggered=lambda: self.transform_text(sort_lines))
        self.dedupe_lines_action = QAction("Remove Duplicate Lines", self, triggered=lambda: self.transform_text(dedupe_lines))

        for action in [
            self.new_note_action,
            self.save_action,
            self.rename_action,
            self.duplicate_action,
            self.pin_action,
            self.archive_action,
            self.find_action,
            self.palette_action,
        ]:
            self.toolbar.addAction(action)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addActions([self.new_note_action, self.open_file_action, self.save_action, self.save_all_action, self.save_file_action, self.export_action])
        file_menu.addSeparator()
        file_menu.addActions([self.archive_action, self.delete_action])

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addActions([self.rename_action, self.duplicate_action, self.clear_action, self.find_action, self.go_to_line_action])
        edit_menu.addSeparator()
        edit_menu.addActions([self.copy_all_action, self.copy_selection_action])

        note_menu = self.menuBar().addMenu("Note")
        note_menu.addActions([self.pin_action, self.favorite_action])
        templates = note_menu.addMenu("Insert Template")
        for name in TEMPLATES:
            templates.addAction(QAction(name, self, triggered=lambda _checked=False, n=name: self.insert_template(n)))

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addActions([
            self.format_json_act,
            self.minify_json_act,
            self.trim_spaces_action,
            self.tabs_to_spaces_action,
            self.spaces_to_tabs_action,
            self.uppercase_action,
            self.lowercase_action,
            self.sort_lines_action,
            self.dedupe_lines_action,
        ])

        view_menu = self.menuBar().addMenu("View")
        view_menu.addActions([self.toggle_sidebar_action, self.toggle_wrap_action, self.next_tab_action, self.prev_tab_action, self.palette_action])
        theme_menu = view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        for theme in ("dark", "light", "system"):
            action = QAction(theme.title(), self, checkable=True, triggered=lambda _checked=False, t=theme: self.set_theme(t))
            action.setChecked(self.settings.theme == theme)
            theme_group.addAction(action)
            theme_menu.addAction(action)

        language_menu = self.menuBar().addMenu("Language")
        language_menu.addAction(self.auto_detect_language_action)
        language_menu.addSeparator()
        language_group = QActionGroup(self)
        for language in LANGUAGES:
            action = QAction(language, self, checkable=True, triggered=lambda _checked=False, l=language: self.set_current_language(l))
            language_group.addAction(action)
            language_menu.addAction(action)

    def _restore_session(self) -> None:
        notes, active_id = self.store.load_session()
        if not notes:
            existing = self.store.list_notes()
            notes = existing[:1] if existing else [Note(title="Scratch 1")]
        for note in notes:
            self._add_note_tab(note)
        if active_id:
            for index in range(self.tabs.count()):
                if self.tabs.widget(index).property("note_id") == active_id:
                    self.tabs.setCurrentIndex(index)
                    break
        self.refresh_note_list()
        self._current_tab_changed(self.tabs.currentIndex())

    def _add_note_tab(self, note: Note) -> None:
        self.notes[note.id] = note
        editor = CodeEditor(note.language)
        editor.set_editor_font(self.settings.font_family, self.settings.font_size)
        editor.update_tab_width(self.settings.tab_width)
        editor.set_editor_theme(self.settings.theme != "light")
        editor.setLineWrapMode(CodeEditor.LineWrapMode.WidgetWidth if self.settings.wrap_lines else CodeEditor.LineWrapMode.NoWrap)
        editor.setPlainText(note.content)
        editor.document().setModified(False)
        editor.setProperty("note_id", note.id)
        editor.textChanged.connect(lambda note_id=note.id: self._note_text_changed(note_id))
        editor.cursorInfoChanged.connect(self.update_status)
        index = self.tabs.addTab(editor, note.display_title())
        self.tabs.setTabToolTip(index, note.title)
        self.tabs.setCurrentIndex(index)

    def new_note(self) -> None:
        count = len(self.notes) + 1
        note = Note(title=f"Scratch {count}")
        self.store.upsert_note(note)
        self._add_note_tab(note)
        self.refresh_note_list()
        self.save_session()

    def current_editor(self) -> CodeEditor | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def current_note(self) -> Note | None:
        editor = self.current_editor()
        if not editor:
            return None
        return self.notes.get(editor.property("note_id"))

    def _note_text_changed(self, note_id: str) -> None:
        if self._loading:
            return
        note = self.notes.get(note_id)
        editor = self._editor_for_note(note_id)
        if note and editor:
            note.content = editor.toPlainText()
            self.dirty.add(note_id)
            self._set_tab_dirty(note_id, True)
            self.save_label.setText("Unsaved")

    def _editor_for_note(self, note_id: str) -> CodeEditor | None:
        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if editor.property("note_id") == note_id:
                return editor
        return None

    def _tab_index_for_note(self, note_id: str) -> int:
        for index in range(self.tabs.count()):
            if self.tabs.widget(index).property("note_id") == note_id:
                return index
        return -1

    def _set_tab_dirty(self, note_id: str, dirty: bool) -> None:
        index = self._tab_index_for_note(note_id)
        note = self.notes.get(note_id)
        if index >= 0 and note:
            suffix = " *" if dirty else ""
            self.tabs.setTabText(index, note.display_title() + suffix)

    def save_current(self) -> None:
        note = self.current_note()
        if note:
            self._sync_note_from_editor(note.id)
            self.store.upsert_note(note)
            self.dirty.discard(note.id)
            self._set_tab_dirty(note.id, False)
            self.save_label.setText("Saved")
            self.refresh_note_list()
            self.save_session()

    def save_all(self) -> None:
        for note_id in list(self.notes):
            self._sync_note_from_editor(note_id)
            note = self.notes[note_id]
            self.store.upsert_note(note)
            self.dirty.discard(note_id)
            self._set_tab_dirty(note_id, False)
        self.save_label.setText("Autosaved")
        self.refresh_note_list()
        self.save_session()

    def _sync_note_from_editor(self, note_id: str) -> None:
        editor = self._editor_for_note(note_id)
        note = self.notes.get(note_id)
        if editor and note:
            note.content = editor.toPlainText()

    def save_session(self) -> None:
        ids = [self.tabs.widget(i).property("note_id") for i in range(self.tabs.count())]
        active = self.current_note().id if self.current_note() else None
        self.store.save_session(ids, active)

    def close_tab(self, index: int) -> None:
        editor = self.tabs.widget(index)
        note_id = editor.property("note_id")
        if note_id in self.dirty:
            self._sync_note_from_editor(note_id)
            self.store.upsert_note(self.notes[note_id])
            self.dirty.discard(note_id)
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_note()
        self.save_session()

    def rename_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        dialog = RenameDialog(note.title, self)
        if dialog.exec():
            note.title = dialog.title()
            self.dirty.add(note.id)
            self.save_current()

    def duplicate_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        copy = Note(
            title=f"{note.title} Copy",
            content=note.content,
            language=note.language,
            category=note.category,
            pinned=False,
            favorite=note.favorite,
            temporary=note.temporary,
        )
        self.store.upsert_note(copy)
        self._add_note_tab(copy)
        self.refresh_note_list()
        self.save_session()

    def toggle_pin(self) -> None:
        note = self.current_note()
        if note:
            note.pinned = not note.pinned
            self.save_current()
            self.pin_action.setChecked(note.pinned)

    def toggle_favorite(self) -> None:
        note = self.current_note()
        if note:
            note.favorite = not note.favorite
            self.save_current()
            self.favorite_action.setChecked(note.favorite)

    def archive_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        if QMessageBox.question(self, "Archive Note", f"Archive '{note.title}'?") == QMessageBox.StandardButton.Yes:
            self.store.archive_note(note.id)
            self._remove_current_tab()

    def delete_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        if QMessageBox.question(self, "Move to Trash", f"Move '{note.title}' to trash?") == QMessageBox.StandardButton.Yes:
            self.store.soft_delete_note(note.id)
            self._remove_current_tab()

    def _remove_current_tab(self) -> None:
        note = self.current_note()
        index = self.tabs.currentIndex()
        if note:
            self.notes.pop(note.id, None)
            self.dirty.discard(note.id)
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_note()
        self.refresh_note_list()
        self.save_session()

    def clear_note(self) -> None:
        editor = self.current_editor()
        note = self.current_note()
        if editor and note and QMessageBox.question(self, "Clear Note", f"Clear all content in '{note.title}'?") == QMessageBox.StandardButton.Yes:
            editor.clear()

    def refresh_note_list(self) -> None:
        query = self.search_filters.query.text()
        language = self.search_filters.language.currentText()
        notes = self.store.search_notes(
            query=query,
            language=language,
            pinned_only=self.search_filters.pinned.isChecked(),
            favorites_only=self.search_filters.favorite.isChecked(),
        )
        self.note_list.clear()
        for note in notes:
            item = QListWidgetItem(f"{note.display_title()}  [{note.language}]")
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setToolTip(f"{note.category} | updated {note.updated_at}")
            self.note_list.addItem(item)

    def _open_note_from_item(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.ItemDataRole.UserRole)
        existing_index = self._tab_index_for_note(note_id)
        if existing_index >= 0:
            self.tabs.setCurrentIndex(existing_index)
            return
        note = self.store.get_note(note_id)
        if note:
            self._add_note_tab(note)
            self.save_session()

    def _current_tab_changed(self, _index: int) -> None:
        note = self.current_note()
        editor = self.current_editor()
        if not note or not editor:
            return
        self._loading = True
        self.language_combo.setCurrentText(note.language)
        self.category_combo.setCurrentText(note.category)
        self._loading = False
        self.pin_action.setChecked(note.pinned)
        self.favorite_action.setChecked(note.favorite)
        self.lang_label.setText(note.language)
        self.category_label.setText(note.category)
        self.save_label.setText("Unsaved" if note.id in self.dirty else "Saved")
        editor.emit_cursor_info()
        self.save_session()

    def _language_changed(self, language: str) -> None:
        if self._loading:
            return
        self.set_current_language(language)

    def set_current_language(self, language: str) -> None:
        note = self.current_note()
        editor = self.current_editor()
        if note and editor:
            note.language = language
            editor.set_language(language)
            self.lang_label.setText(language)
            self.dirty.add(note.id)
            self.save_current()

    def auto_detect_language(self) -> None:
        note = self.current_note()
        editor = self.current_editor()
        if note and editor:
            self.set_current_language(detect_language(editor.toPlainText(), note.title))

    def _category_changed(self, category: str) -> None:
        if self._loading:
            return
        note = self.current_note()
        if note:
            note.category = category
            self.category_label.setText(category)
            self.dirty.add(note.id)
            self.save_current()

    def update_status(self, line: int, col: int, lines: int, chars: int, selected: int) -> None:
        suffix = f" | Sel {selected}" if selected else ""
        self.cursor_label.setText(f"Ln {line}, Col {col}{suffix}")
        self.count_label.setText(f"Lines {lines} | Chars {chars}")

    def show_find(self) -> None:
        self.find_bar.setVisible(True)
        self.find_bar.find_input.setFocus()
        editor = self.current_editor()
        if editor and editor.textCursor().hasSelection():
            self.find_bar.find_input.setText(editor.textCursor().selectedText())

    def find_next(self, backwards: bool = False) -> None:
        editor = self.current_editor()
        text = self.find_bar.find_input.text()
        if not editor or not text:
            return
        find_flags = QTextDocument.FindFlag.FindBackward if backwards else QTextDocument.FindFlag(0)
        found = editor.find(text, find_flags)
        if not found:
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End if backwards else QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            editor.find(text, find_flags)

    def replace_one(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_bar.find_input.text():
            cursor.insertText(self.find_bar.replace_input.text())
        self.find_next(False)

    def replace_all(self) -> None:
        editor = self.current_editor()
        find = self.find_bar.find_input.text()
        if not editor or not find:
            return
        text = editor.toPlainText().replace(find, self.find_bar.replace_input.text())
        editor.setPlainText(text)

    def go_to_line(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        dialog = GoToLineDialog(editor.blockCount(), self)
        if dialog.exec():
            block = editor.document().findBlockByNumber(dialog.line() - 1)
            if block.isValid():
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.setFocus()

    def transform_text(self, func) -> None:
        editor = self.current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        try:
            if cursor.hasSelection():
                cursor.insertText(func(cursor.selectedText().replace("\u2029", "\n")))
            else:
                editor.setPlainText(func(editor.toPlainText()))
        except Exception as exc:
            QMessageBox.warning(self, "Transform Failed", str(exc))

    def format_json_action(self) -> None:
        self.transform_text(format_json)
        self.set_current_language("JSON")

    def minify_json_action(self) -> None:
        self.transform_text(minify_json)
        self.set_current_language("JSON")

    def copy_entire_note(self) -> None:
        editor = self.current_editor()
        if editor:
            QApplication.clipboard().setText(editor.toPlainText())
            self.status.showMessage("Copied entire note", 2000)

    def insert_template(self, name: str) -> None:
        editor = self.current_editor()
        if editor:
            editor.insertPlainText(TEMPLATES[name])
            detected = detect_language(TEMPLATES[name], name)
            if detected != "Plain Text":
                self.set_current_language(detected)

    def open_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Text or Code File",
            str(Path.home()),
            "Text and Code Files (*.txt *.md *.json *.py *.js *.ts *.sql *.html *.css *.yaml *.yml *.sh);;All Files (*)",
        )
        if not path:
            return
        file_path = Path(path)
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")
        note = Note(title=file_path.name, content=content, language=detect_language(content, file_path.name), category="Code", temporary=False, file_path=str(file_path))
        self.store.upsert_note(note)
        self._add_note_tab(note)
        self.refresh_note_list()
        self.save_session()

    def save_to_file(self) -> None:
        note = self.current_note()
        editor = self.current_editor()
        if not note or not editor:
            return
        path = note.file_path
        if not path:
            path, _filter = QFileDialog.getSaveFileName(self, "Save Note to File", str(Path.home() / f"{note.title}.txt"))
        if not path:
            return
        Path(path).write_text(editor.toPlainText(), encoding="utf-8")
        note.file_path = path
        note.temporary = False
        self.save_current()
        self.status.showMessage(f"Saved to {path}", 3000)

    def export_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        path, _filter = QFileDialog.getSaveFileName(self, "Export Note", str(Path.home() / f"{note.title}.txt"))
        if path:
            Path(path).write_text(self.current_editor().toPlainText(), encoding="utf-8")

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_wrap(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        wrap = editor.lineWrapMode() == CodeEditor.LineWrapMode.NoWrap
        editor.setLineWrapMode(CodeEditor.LineWrapMode.WidgetWidth if wrap else CodeEditor.LineWrapMode.NoWrap)
        self.settings.set("wrap_lines", wrap)

    def _move_tab(self, delta: int) -> None:
        if self.tabs.count() <= 1:
            return
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + delta) % self.tabs.count())

    def open_palette(self) -> None:
        commands = [
            "New Note",
            "Rename Note",
            "Duplicate Note",
            "Pin Note",
            "Favorite Note",
            "Archive Note",
            "Format JSON",
            "Minify JSON",
            "Auto Detect Language",
            "Toggle Sidebar",
            "Toggle Line Wrap",
            "Dark Mode",
            "Light Mode",
        ]
        commands.extend([f"Language: {language}" for language in LANGUAGES])
        commands.extend([f"Template: {name}" for name in TEMPLATES])
        dialog = CommandPalette(commands, self)
        if dialog.exec():
            self._run_command(dialog.selected_command())

    def _run_command(self, command: str | None) -> None:
        if not command:
            return
        mapping = {
            "New Note": self.new_note,
            "Rename Note": self.rename_note,
            "Duplicate Note": self.duplicate_note,
            "Pin Note": self.toggle_pin,
            "Favorite Note": self.toggle_favorite,
            "Archive Note": self.archive_note,
            "Format JSON": self.format_json_action,
            "Minify JSON": self.minify_json_action,
            "Auto Detect Language": self.auto_detect_language,
            "Toggle Sidebar": self.toggle_sidebar,
            "Toggle Line Wrap": self.toggle_wrap,
            "Dark Mode": lambda: self.set_theme("dark"),
            "Light Mode": lambda: self.set_theme("light"),
        }
        if command.startswith("Language: "):
            self.set_current_language(command.split(": ", 1)[1])
        elif command.startswith("Template: "):
            self.insert_template(command.split(": ", 1)[1])
        elif command in mapping:
            mapping[command]()

    def set_theme(self, theme: str) -> None:
        self.settings.set("theme", theme)
        self._apply_theme(theme)

    def _apply_theme(self, theme: str) -> None:
        if theme == "light":
            self.setStyleSheet(LIGHT_STYLE)
        else:
            self.setStyleSheet(DARK_STYLE)
        dark = theme != "light"
        if not hasattr(self, "tabs"):
            return
        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if isinstance(editor, CodeEditor):
                editor.set_editor_theme(dark)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.ApplicationDeactivate:
            self.save_all()
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        self.save_all()
        self.store.close()
        event.accept()


DARK_STYLE = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }
QPlainTextEdit { background: #0d1117; color: #c9d1d9; selection-background-color: #264f78; padding: 8px; }
QTabWidget::pane { border-top: 1px solid #30363d; }
QTabBar::tab { background: #161b22; color: #c9d1d9; padding: 7px 12px; border: 1px solid #30363d; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #0d1117; }
QLineEdit, QComboBox, QListWidget { background: #161b22; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 5px; }
QPushButton, QToolButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; }
QPushButton:hover, QToolButton:hover { background: #30363d; }
QMenuBar, QMenu { background: #161b22; color: #c9d1d9; }
QStatusBar, QToolBar { background: #161b22; border-top: 1px solid #30363d; }
"""

LIGHT_STYLE = """
QMainWindow, QWidget { background: #ffffff; color: #24292f; }
QPlainTextEdit { background: #ffffff; color: #24292f; selection-background-color: #b6d7ff; padding: 8px; }
QTabWidget::pane { border-top: 1px solid #d0d7de; }
QTabBar::tab { background: #f6f8fa; color: #24292f; padding: 7px 12px; border: 1px solid #d0d7de; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #ffffff; }
QLineEdit, QComboBox, QListWidget { background: #ffffff; color: #24292f; border: 1px solid #d0d7de; border-radius: 6px; padding: 5px; }
QPushButton, QToolButton { background: #f6f8fa; color: #24292f; border: 1px solid #d0d7de; border-radius: 6px; padding: 5px 10px; }
QPushButton:hover, QToolButton:hover { background: #eaeef2; }
QMenuBar, QMenu { background: #ffffff; color: #24292f; }
QStatusBar, QToolBar { background: #f6f8fa; border-top: 1px solid #d0d7de; }
"""
