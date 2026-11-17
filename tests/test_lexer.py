"""Tests for the MECSL lexer."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.lexer.token import TokenKind


def lex(src: str) -> tuple[list, DiagnosticBag]:
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    return tokens, bag


def kinds(tokens) -> list[str]:
    return [t.kind.name for t in tokens]


# ----------------------------------------------------------------- basic tokens
def test_eof_on_empty():
    toks, bag = lex("")
    assert toks[-1].kind == TokenKind.EOF
    assert not bag.has_errors


def test_integer():
    toks, bag = lex("42")
    assert toks[0].kind == TokenKind.INTEGER
    assert toks[0].value == 42
    assert not bag.has_errors


def test_string():
    toks, bag = lex('"hello"')
    assert toks[0].kind == TokenKind.STRING
    assert toks[0].value == "hello"


def test_string_escaped():
    toks, bag = lex(r'"hello\nworld"')
    assert toks[0].value == "hello\nworld"


def test_true_false():
    toks, bag = lex("true false")
    assert toks[0].kind == TokenKind.TRUE
    assert toks[0].value is True
    assert toks[1].kind == TokenKind.FALSE
    assert toks[1].value is False


# ----------------------------------------------------------------- keywords
def test_keywords():
    src = "import macro script print run env"
    toks, _ = lex(src)
    expected = ["IMPORT", "MACRO", "SCRIPT", "PRINT", "RUN", "ENV", "EOF"]
    assert kinds(toks) == expected


def test_identifier_not_keyword():
    toks, _ = lex("myVar")
    assert toks[0].kind == TokenKind.IDENTIFIER
    assert toks[0].lexeme == "myVar"


# ----------------------------------------------------------------- punctuation
def test_punctuation():
    src = "{ } [ ] ( ) , . = ;"
    toks, _ = lex(src)
    exp = ["LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
           "LPAREN", "RPAREN", "COMMA", "DOT", "EQUALS", "SEMICOLON", "EOF"]
    assert kinds(toks) == exp


# ----------------------------------------------------------------- comments
def test_comment_skipped():
    toks, bag = lex("# this is a comment\n42")
    assert toks[0].kind == TokenKind.INTEGER
    assert not bag.has_errors


def test_inline_comment():
    toks, _ = lex("42 # comment")
    assert toks[0].kind == TokenKind.INTEGER
    assert toks[1].kind == TokenKind.EOF


# ----------------------------------------------------------------- line tracking
def test_line_tracking():
    src = "a\nb\nc"
    toks, _ = lex(src)
    lines = [t.source_span.start_line for t in toks if t.kind != TokenKind.EOF]
    assert lines == [1, 2, 3]


def test_column_tracking():
    toks, _ = lex("abc def")
    assert toks[0].source_span.start_column == 1
    assert toks[1].source_span.start_column == 5


# ----------------------------------------------------------------- errors
def test_invalid_character():
    toks, bag = lex("@")
    assert bag.has_errors
    errors = [d for d in bag.items if d.code == "E101"]
    assert errors


def test_unterminated_string():
    toks, bag = lex('"no close')
    assert bag.has_errors
    errors = [d for d in bag.items if d.code == "E102"]
    assert errors


def test_eof_always_appended():
    toks, _ = lex("x = 1;")
    assert toks[-1].kind == TokenKind.EOF


# ----------------------------------------------------------------- composite
def test_section_tokens():
    src = '[server] { host = "localhost"; }'
    toks, bag = lex(src)
    assert not bag.has_errors
    assert toks[0].kind == TokenKind.LBRACKET
    assert toks[1].kind == TokenKind.IDENTIFIER
    assert toks[1].lexeme == "server"
