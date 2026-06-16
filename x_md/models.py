from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Media:
    url: str | None = None
    alt_text: str | None = None
    source_path: Path | None = None
    relative_path: str | None = None


@dataclass
class Post:
    id: str
    text: str = ""
    author_id: str | None = None
    author_handle: str | None = None
    author_name: str | None = None
    created_at: str | None = None
    url: str | None = None
    parent_id: str | None = None
    quoted_id: str | None = None
    media: list[Media] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def author_key(self) -> str:
        if self.author_id:
            return f"id:{self.author_id}"
        if self.author_handle:
            return f"handle:{self.author_handle.lower()}"
        return "unknown"

    @property
    def display_author(self) -> str:
        if self.author_name and self.author_handle:
            return f"{self.author_name} @{self.author_handle}"
        if self.author_name:
            return self.author_name
        if self.author_handle:
            return f"@{self.author_handle}"
        return "unknown author"


@dataclass
class ExtractionResult:
    posts: dict[str, Post]
    media_files: list[Path]
