"""Lexical analyser for MECSL."""

from __future__ import annotations

import re
from typing import Iterator

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import SourceSpan
from mecsl.lexer.token import Token, TokenKind, keyword_or_identifier


class Lexer:
    """Converts raw source text into a flat list of tokens."""

    def __init__(self, source: str, filename: str, bag: DiagnosticBag) -> None:
        self._src = source
        self._filename = filename
        self._bag = bag
        self._pos = 0
        self._line = 1
        self._col = 1

    # ------------------------------------------------------------------ public
    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            tok = self._next_token()
            tokens.append(tok)
            if tok.kind == TokenKind.EOF:
                break
        return tokens

    # ----------------------------------------------------------------- private
    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        return self._src[idx] if idx < len(self._src) else ""

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _span_from(self, sl: int, sc: int) -> SourceSpan:
        return SourceSpan(self._filename, sl, sc, self._line, self._col)

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < len(self._src):
            ch = self._peek()
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            elif ch == "#":
                # Line comment — consume until newline
                while self._pos < len(self._src) and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _next_token(self) -> Token:
        self._skip_whitespace_and_comments()

        sl, sc = self._line, self._col

        if self._pos >= len(self._src):
            return Token(TokenKind.EOF, "", None, self._span_from(sl, sc))

        ch = self._peek()

        # String literal
        if ch == '"':
            return self._lex_string(sl, sc)

        # Integer literal
        if ch.isdigit():
            return self._lex_integer(sl, sc)

        # Identifier or keyword
        if ch.isalpha() or ch == "_":
            return self._lex_identifier(sl, sc)

        # Single-character punctuation
        punct = {
            "{": TokenKind.LBRACE,
            "}": TokenKind.RBRACE,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            ",": TokenKind.COMMA,
            ".": TokenKind.DOT,
            "=": TokenKind.EQUALS,
            ";": TokenKind.SEMICOLON,
        }
        if ch in punct:
            self._advance()
            return Token(punct[ch], ch, None, self._span_from(sl, sc))

        # Unknown character
        self._advance()
        span = self._span_from(sl, sc)
        self._bag.error(
            "E101",
            f"Invalid character {ch!r}",
            span,
            suggestion="Remove or replace the unexpected character.",
        )
        # Return a placeholder and continue lexing
        return self._next_token()

    # ----------------------------------------------------------------- helpers
    def _lex_string(self, sl: int, sc: int) -> Token:
        self._advance()  # consume opening "
        buf: list[str] = []
        while self._pos < len(self._src):
            ch = self._peek()
            if ch == '"':
                self._advance()  # consume closing "
                lexeme = '"' + "".join(buf) + '"'
                return Token(
                    TokenKind.STRING, lexeme, "".join(buf), self._span_from(sl, sc)
                )
            if ch == "\\":
                self._advance()  # consume backslash
                esc = self._peek()
                escape_map = {
                    "n": "\n", "t": "\t", "r": "\r",
                    '"': '"', "\\": "\\",
                }
                if esc in escape_map:
                    buf.append(escape_map[esc])
                    self._advance()
                else:
                    buf.append("\\")
                    buf.append(esc)
                    self._advance()
            elif ch == "\n":
                # Newline inside string — treat as unterminated
                break
            else:
                buf.append(ch)
                self._advance()

        span = self._span_from(sl, sc)
        self._bag.error(
            "E102",
            "Unterminated string literal",
            span,
            suggestion='Add a closing double-quote (") to end the string.',
        )
        return Token(TokenKind.STRING, '"' + "".join(buf), "".join(buf), span)

    def _lex_integer(self, sl: int, sc: int) -> Token:
        digits: list[str] = []
        while self._pos < len(self._src) and self._peek().isdigit():
            digits.append(self._advance())
        lexeme = "".join(digits)
        return Token(TokenKind.INTEGER, lexeme, int(lexeme), self._span_from(sl, sc))

    def _lex_identifier(self, sl: int, sc: int) -> Token:
        chars: list[str] = []
        while self._pos < len(self._src) and (
            self._peek().isalnum() or self._peek() == "_"
        ):
            chars.append(self._advance())
        lexeme = "".join(chars)
        kind = keyword_or_identifier(lexeme)
        value = (
            True if kind == TokenKind.TRUE
            else False if kind == TokenKind.FALSE
            else None
        )
        return Token(kind, lexeme, value, self._span_from(sl, sc))
