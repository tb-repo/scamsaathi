"""Prompt loading and untrusted-data delimiting (Phase 4).

Prompts are stored as markdown files with a ``PROMPT_ID: <name>/<version>`` header.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_PROMPTS_DIR: Final = Path(__file__).parent
_ID_RE: Final = re.compile(r"^PROMPT_ID:\s*([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)", re.MULTILINE)

CURRENT: Final[dict[str, str]] = {
    "extract": "v1",
    "classify": "v2",
    "explain": "v1",
    "interview": "v1",
}


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str

    @property
    def id(self) -> str:
        return f"{self.name}/{self.version}"


def load_prompt(name: str, version: str | None = None) -> Prompt:
    """Load a prompt template from disk by name and version."""
    v = version or CURRENT.get(name)
    if not v:
        raise ValueError(f"Unknown prompt {name!r} (not in CURRENT)")

    path = _PROMPTS_DIR / f"{name}_{v}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    m = _ID_RE.search(raw)
    if not m:
        raise ValueError(f"Prompt {path.name} is missing a valid PROMPT_ID header")

    parsed_name, parsed_version = m.group(1), m.group(2)
    return Prompt(name=parsed_name, version=parsed_version, text=raw.strip())


def untrusted_block(text: str) -> str:
    """Safely delimit untrusted user content, preventing premature tag closure."""
    sanitized = text.replace("</user_content>", "[tag removed]")
    return f"<user_content>\n{sanitized}\n</user_content>"


__all__ = ["CURRENT", "Prompt", "load_prompt", "untrusted_block"]

