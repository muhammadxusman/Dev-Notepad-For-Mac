from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QStandardPaths

from .models import Note, utc_now_iso


def app_data_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    path = Path(base or Path.home() / "Library" / "Application Support" / "DevScratchpad")
    path.mkdir(parents=True, exist_ok=True)
    return path


class NoteStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or app_data_dir() / "notes.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'Plain Text',
                category TEXT NOT NULL DEFAULT 'Temp',
                pinned INTEGER NOT NULL DEFAULT 0,
                favorite INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0,
                temporary INTEGER NOT NULL DEFAULT 1,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                file_path TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_tabs (
                note_id TEXT PRIMARY KEY,
                tab_order INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()

    def upsert_note(self, note: Note) -> None:
        note.updated_at = utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO notes (
                id, title, content, language, category, pinned, favorite, archived,
                deleted, temporary, expires_at, created_at, updated_at, file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                language=excluded.language,
                category=excluded.category,
                pinned=excluded.pinned,
                favorite=excluded.favorite,
                archived=excluded.archived,
                deleted=excluded.deleted,
                temporary=excluded.temporary,
                expires_at=excluded.expires_at,
                updated_at=excluded.updated_at,
                file_path=excluded.file_path
            """,
            (
                note.id,
                note.title,
                note.content,
                note.language,
                note.category,
                int(note.pinned),
                int(note.favorite),
                int(note.archived),
                int(note.deleted),
                int(note.temporary),
                note.expires_at,
                note.created_at,
                note.updated_at,
                note.file_path,
            ),
        )
        self._conn.commit()

    def note_from_row(self, row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            language=row["language"],
            category=row["category"],
            pinned=bool(row["pinned"]),
            favorite=bool(row["favorite"]),
            archived=bool(row["archived"]),
            deleted=bool(row["deleted"]),
            temporary=bool(row["temporary"]),
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            file_path=row["file_path"],
        )

    def get_note(self, note_id: str) -> Optional[Note]:
        row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self.note_from_row(row) if row else None

    def list_notes(self, include_archived: bool = False, include_deleted: bool = False) -> list[Note]:
        clauses = []
        if not include_archived:
            clauses.append("archived = 0")
        if not include_deleted:
            clauses.append("deleted = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM notes {where} ORDER BY pinned DESC, updated_at DESC"
        ).fetchall()
        return [self.note_from_row(row) for row in rows]

    def search_notes(
        self,
        query: str = "",
        language: str = "All",
        pinned_only: bool = False,
        favorites_only: bool = False,
    ) -> list[Note]:
        clauses = ["deleted = 0", "archived = 0"]
        params: list[object] = []
        if query:
            clauses.append("(lower(title) LIKE ? OR lower(content) LIKE ?)")
            needle = f"%{query.lower()}%"
            params.extend([needle, needle])
        if language != "All":
            clauses.append("language = ?")
            params.append(language)
        if pinned_only:
            clauses.append("pinned = 1")
        if favorites_only:
            clauses.append("favorite = 1")
        rows = self._conn.execute(
            f"SELECT * FROM notes WHERE {' AND '.join(clauses)} ORDER BY pinned DESC, updated_at DESC",
            params,
        ).fetchall()
        return [self.note_from_row(row) for row in rows]

    def archive_note(self, note_id: str) -> None:
        self._conn.execute(
            "UPDATE notes SET archived = 1, category = 'Archive', updated_at = ? WHERE id = ?",
            (utc_now_iso(), note_id),
        )
        self._conn.commit()

    def soft_delete_note(self, note_id: str) -> None:
        self._conn.execute(
            "UPDATE notes SET deleted = 1, updated_at = ? WHERE id = ?",
            (utc_now_iso(), note_id),
        )
        self._conn.execute("DELETE FROM session_tabs WHERE note_id = ?", (note_id,))
        self._conn.commit()

    def save_session(self, note_ids: Iterable[str], active_note_id: Optional[str]) -> None:
        self._conn.execute("DELETE FROM session_tabs")
        for order, note_id in enumerate(note_ids):
            self._conn.execute(
                "INSERT INTO session_tabs(note_id, tab_order, active) VALUES (?, ?, ?)",
                (note_id, order, int(note_id == active_note_id)),
            )
        self._conn.commit()

    def load_session(self) -> tuple[list[Note], Optional[str]]:
        rows = self._conn.execute(
            """
            SELECT n.*, s.active FROM session_tabs s
            JOIN notes n ON n.id = s.note_id
            WHERE n.deleted = 0
            ORDER BY s.tab_order ASC
            """
        ).fetchall()
        active_id = None
        notes = []
        for row in rows:
            note = self.note_from_row(row)
            notes.append(note)
            if row["active"]:
                active_id = note.id
        return notes, active_id

