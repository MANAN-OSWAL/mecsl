"""Tests for semantic analysis."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.macro.processor import MacroProcessor
from mecsl.symbols.tables import SymbolTable
from mecsl.semantic.analyzer import SemanticAnalyzer


def analyze(src: str):
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    prog = Parser(tokens, "<test>", bag).parse()
    mp = MacroProcessor(bag)
    mp.collect_definitions(prog)
    expanded = mp.expand_program(prog)
    table = SymbolTable("test", bag)
    table.build_from_program(expanded)
    analyzer = SemanticAnalyzer(table, bag)
    analyzer.analyze(expanded)
    return bag


def test_valid_section_passes():
    bag = analyze('[s] { x = "hello"; }')
    assert not bag.has_errors


def test_undefined_reference_caught():
    bag = analyze('[app] { host = missing.key; }')
    assert bag.has_errors
    assert any(d.code == "E203" for d in bag.items)


def test_defined_reference_passes():
    src = '[server] { host = "localhost"; } [app] { h = server.host; }'
    bag = analyze(src)
    assert not bag.has_errors


def test_env_correct_usage():
    bag = analyze('[s] { port = env("PORT", 8080); }')
    assert not bag.has_errors


def test_env_wrong_arg_count():
    bag = analyze('[s] { port = env(); }')
    assert bag.has_errors
    assert any(d.code == "E302" for d in bag.items)


def test_duplicate_script_name():
    src = 'script start { print "a"; } script start { print "b"; }'
    bag = analyze(src)
    assert bag.has_errors
    assert any(d.code == "E204" for d in bag.items)


def test_run_requires_string():
    # run with a string literal should be valid
    bag = analyze('script s { run "app"; }')
    assert not bag.has_errors
