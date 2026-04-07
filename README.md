# Dev Scratchpad

Dev Scratchpad is a local-first macOS desktop notepad for developer scratch work: code snippets, terminal commands, SQL queries, API payloads, JSON samples, regex patterns, debugging notes, and short-lived meeting notes.

It is intentionally lighter than an IDE or document editor. Notes autosave into a local SQLite database and the previous tab session is restored on launch.

## Features

- Multi-tab notes with reorderable and closable tabs
- Local SQLite persistence in the macOS app data folder
- Autosave every 3 seconds, on app deactivation, and on close
- Session restore for last-open tabs
- Sidebar note search with language, pinned, and favorite filters
- Monospace code editor with line numbers, current-line highlight, indentation helpers, undo/redo, line wrap toggle, find/replace, and go to line
- Lightweight syntax highlighting for Python, JavaScript, TypeScript, JSON, HTML, CSS, Bash, SQL, YAML, Markdown, and plain text
- Language mode and category dropdowns
- Manual language auto-detection for pasted content
- Pinned and favorite notes
- Archive and trash-oriented deletion flow
- Developer utilities: format/minify JSON, trim trailing spaces, tabs/spaces conversion, uppercase/lowercase, sort lines, remove duplicate lines
- Snippet templates for Python, JSON, SQL, Bash, API request, Markdown checklist, and `.env` samples
- File import/open, save to file, and export
- Dark and light themes
- Basic command palette

## Project Structure

```text
dev_scratchpad/
  app/
    __init__.py
    main.py           # QApplication entry point
    main_window.py    # Menus, toolbar, tabs, sidebar, autosave, file actions
    editor.py         # QPlainTextEdit-based code editor with line numbers
    syntax.py         # Lightweight regex syntax highlighter
    dialogs.py        # Find/replace bar, rename, go-to-line, command palette
    models.py         # Note dataclass and app constants
    storage.py        # SQLite storage and session restore
    settings.py       # QSettings wrapper
    text_utils.py     # JSON formatting, line transforms, templates, detection
  docs/
    packaging.md
  pyproject.toml
  requirements.txt
  README.md
```

## Setup on macOS

Python 3.10 or newer is required. Python 3.12 was used for the local smoke test.

```bash
cd "/Users/usmanali/Desktop/untitled folder/dev_scratchpad"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
cd "/Users/usmanali/Desktop/untitled folder/dev_scratchpad"
.venv/bin/python -m app.main
```

The app stores notes locally via `QStandardPaths.AppDataLocation`, which maps to a user-local application support path on macOS. Notes remain offline and private by default.

## Keyboard Shortcuts

- `Cmd+N`: new note
- `Cmd+S`: save current note
- `Ctrl+Cmd+S`: save all notes
- `Cmd+F`: find/replace
- `Cmd+L`: go to line
- `Cmd+R`: rename note
- `Cmd+D`: duplicate note
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: next/previous tab
- `Cmd+B`: toggle sidebar
- `Option+Z`: toggle line wrap
- `Cmd+Shift+P`: command palette

## Module Notes

`storage.py` owns the SQLite schema, note CRUD operations, search, archive/delete flags, and session tab persistence.

`main_window.py` wires the product behavior: tab lifecycle, autosave, sidebar filtering, note metadata controls, menu actions, file import/export, command palette dispatch, and status bar updates.

`editor.py` extends `QPlainTextEdit` with line numbers, current-line highlighting, tab indentation, automatic indentation after common opening characters, and cursor statistics.

`syntax.py` provides a small regex highlighter. It is intentionally lightweight and can be extended without turning the app into a full IDE.

`text_utils.py` contains pure text transforms and snippet templates, keeping developer utility behavior easy to test and extend.
