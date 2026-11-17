"""Diagnostic (error/warning) infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from mecsl.source import SourceSpan


class Severity(Enum):
    ERROR = auto()
    WARNING = auto()
    NOTE = auto()


@dataclass
class Diagnostic:
    code: str          # e.g. "E101"
    message: str
    span: SourceSpan
    severity: Severity = Severity.ERROR
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        sev = self.severity.name
        loc = f"{self.span.file}:{self.span.start_line}:{self.span.start_column}"
        base = f"[{self.code}] {sev}: {loc}: {self.message}"
        if self.suggestion:
            base += f"\n  Suggestion: {self.suggestion}"
        return base


class DiagnosticError(Exception):
    """Raised when one or more fatal diagnostics have been emitted."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__(
            "\n".join(str(d) for d in diagnostics)
        )


class DiagnosticBag:
    """Collects diagnostics; can be flushed or raised."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    # ------------------------------------------------------------------ emit
    def error(
        self,
        code: str,
        message: str,
        span: SourceSpan,
        suggestion: Optional[str] = None,
    ) -> None:
        self._items.append(
            Diagnostic(code, message, span, Severity.ERROR, suggestion)
        )

    def warning(
        self,
        code: str,
        message: str,
        span: SourceSpan,
        suggestion: Optional[str] = None,
    ) -> None:
        self._items.append(
            Diagnostic(code, message, span, Severity.WARNING, suggestion)
        )

    # ------------------------------------------------------------------ query
    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self._items)

    @property
    def items(self) -> list[Diagnostic]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    # ---------------------------------------------------------------- raise
    def raise_if_errors(self) -> None:
        errors = [d for d in self._items if d.severity == Severity.ERROR]
        if errors:
            raise DiagnosticError(errors)
