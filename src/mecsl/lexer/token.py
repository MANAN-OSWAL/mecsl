"""Token types and Token dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from mecsl.source import SourceSpan


class TokenKind(Enum):
    # Literals
    INTEGER    = auto()
    STRING     = auto()
    TRUE       = auto()
    FALSE      = auto()
    # Keywords
    IMPORT     = auto()
    MACRO      = auto()
    SCRIPT     = auto()
    PRINT      = auto()
    RUN        = auto()
    ENV        = auto()
    # Identifiers
    IDENTIFIER = auto()
    # Punctuation
    LBRACE     = auto()  # {
    RBRACE     = auto()  # }
    LBRACKET   = auto()  # [
    RBRACKET   = auto()  # ]
    LPAREN     = auto()  # (
    RPAREN     = auto()  # )
    COMMA      = auto()  # ,
    DOT        = auto()  # .
    EQUALS     = auto()  # =
    SEMICOLON  = auto()  # ;
    # Sentinel
    EOF        = auto()


_KEYWORDS: dict[str, TokenKind] = {
    "import": TokenKind.IMPORT,
    "macro":  TokenKind.MACRO,
    "script": TokenKind.SCRIPT,
    "print":  TokenKind.PRINT,
    "run":    TokenKind.RUN,
    "env":    TokenKind.ENV,
    "true":   TokenKind.TRUE,
    "false":  TokenKind.FALSE,
}


def keyword_or_identifier(lexeme: str) -> TokenKind:
    return _KEYWORDS.get(lexeme, TokenKind.IDENTIFIER)


@dataclass(slots=True)
class Token:
    kind: TokenKind
    lexeme: str
    value: Any          # Python value for literals; None otherwise
    source_span: SourceSpan

    def __repr__(self) -> str:
        return (
            f"Token({self.kind.name!r}, {self.lexeme!r}, "
            f"value={self.value!r}, span={self.source_span})"
        )
