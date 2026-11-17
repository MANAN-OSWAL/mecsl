"""Tests for symbol table construction."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.macro.processor import MacroProcessor
from mecsl.symbols.tables import SymbolTable, SymbolKind


def build_table(src: str):
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    prog = Parser(tokens, "<test>", bag).parse()
    mp = MacroProcessor(bag)
    mp.collect_definitions(prog)
    expanded = mp.expand_program(prog)
    table = SymbolTable("test_mod", bag)
    table.build_from_program(expanded)
    return table, bag


def test_section_registered():
    table, bag = build_table('[server] { host = "localhost"; }')
    sym = table.lookup("server")
    assert sym is not None
    assert sym.kind == SymbolKind.SECTION


def test_key_registered():
    table, bag = build_table('[server] { host = "localhost"; }')
    sym = table.lookup("server.host")
    assert sym is not None
    assert sym.kind == SymbolKind.KEY
    assert sym.type == "string"


def test_integer_type():
    table, bag = build_table('[server] { port = 8080; }')
    sym = table.lookup("server.port")
    assert sym.type == "integer"


def test_boolean_type():
    table, bag = build_table('[cfg] { flag = true; }')
    sym = table.lookup("cfg.flag")
    assert sym.type == "boolean"


def test_reference_type():
    table, bag = build_table('[app] { host = server.host; }')
    sym = table.lookup("app.host")
    assert sym.type == "reference"


def test_env_type():
    table, bag = build_table('[cfg] { port = env("PORT", 8080); }')
    sym = table.lookup("cfg.port")
    assert sym.type == "env"


def test_script_registered():
    table, bag = build_table('script start { print "hi"; }')
    sym = table.lookup("script:start")
    assert sym is not None
    assert sym.kind == SymbolKind.SCRIPT


def test_duplicate_key_error():
    src = '[s] { x = 1; x = 2; }'
    table, bag = build_table(src)
    assert bag.has_errors
    assert any(d.code == "E204" for d in bag.items)


def test_all_symbols_sorted():
    table, bag = build_table('[b] { z = 1; a = 2; }')
    names = [s.qualified_name for s in table.all_symbols()]
    assert names == sorted(names)
