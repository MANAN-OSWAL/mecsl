"""Source-span tracking for diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open range inside a source file."""

    file: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __str__(self) -> str:
        return f"{self.file}:{self.start_line}:{self.start_column}"

    # Convenience factory for a single-character position.
    @classmethod
    def point(cls, file: str, line: int, col: int) -> "SourceSpan":
        return cls(file, line, col, line, col)

    # Merge two spans (same file assumed).
    def merge(self, other: "SourceSpan") -> "SourceSpan":
        return SourceSpan(
            self.file,
            self.start_line,
            self.start_column,
            other.end_line,
            other.end_column,
        )


UNKNOWN_SPAN = SourceSpan("<unknown>", 0, 0, 0, 0)
