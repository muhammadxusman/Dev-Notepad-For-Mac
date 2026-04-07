from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Note:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "Untitled"
    content: str = ""
    language: str = "Plain Text"
    category: str = "Temp"
    pinned: bool = False
    favorite: bool = False
    archived: bool = False
    deleted: bool = False
    temporary: bool = True
    expires_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    file_path: Optional[str] = None

    def display_title(self) -> str:
        prefix = "* " if self.favorite else ""
        pin = "[pin] " if self.pinned else ""
        return f"{pin}{prefix}{self.title or 'Untitled'}"


LANGUAGES = [
    "Plain Text",
    "Python",
    "JavaScript",
    "TypeScript",
    "JSON",
    "HTML",
    "CSS",
    "Bash",
    "SQL",
    "YAML",
    "Markdown",
]


CATEGORIES = ["Code", "Commands", "SQL", "API", "Debug", "Temp", "Personal", "Archive"]
