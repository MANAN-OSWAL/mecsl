"""Tests for the MECSL parser."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.parser.ast import (
    ProgramNode, ImportNode, SectionNode, AssignmentNode,
    MacroDefinitionNode, MacroCallNode, ScriptNode,
    LiteralNode, ReferenceNode, FunctionCallNode, ListNode, IdentifierNode,
)


def parse(src: str) -> tuple[ProgramNode, DiagnosticBag]:
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    program = Parser(tokens, "<test>", bag).parse()
    return program, bag


# ----------------------------------------------------------------- import
def test_parse_import():
    prog, bag = parse('import "common.mecs";')
    assert not bag.has_errors
    assert len(prog.statements) == 1
    node = prog.statements[0]
    assert isinstance(node, ImportNode)
    assert node.path == "common.mecs"


# ----------------------------------------------------------------- section
def test_parse_section_with_assignment():
    src = '[server] { host = "localhost"; port = 8080; }'
    prog, bag = parse(src)
    assert not bag.has_errors
    assert isinstance(prog.statements[0], SectionNode)
    sec = prog.statements[0]
    assert sec.name == "server"
    assert len(sec.body) == 2
    assert sec.body[0].target == ["host"]
    assert isinstance(sec.body[0].value, LiteralNode)
    assert sec.body[0].value.value == "localhost"


# ----------------------------------------------------------------- literals
def test_literal_boolean():
    prog, bag = parse("[f] { a = true; b = false; }")
    assert not bag.has_errors
    sec = prog.statements[0]
    assert sec.body[0].value.value is True
    assert sec.body[1].value.value is False


def test_literal_list():
    prog, bag = parse('[s] { tags = ["a", "b"]; }')
    assert not bag.has_errors
    val = prog.statements[0].body[0].value
    assert isinstance(val, ListNode)
    assert len(val.elements) == 2


# ----------------------------------------------------------------- reference
def test_qualified_reference():
    prog, bag = parse('[app] { host = server_defaults.host; }')
    assert not bag.has_errors
    val = prog.statements[0].body[0].value
    assert isinstance(val, ReferenceNode)
    assert val.qualified_name == "server_defaults.host"


# ----------------------------------------------------------------- env
def test_env_function():
    prog, bag = parse('[s] { port = env("PORT", 8080); }')
    assert not bag.has_errors
    val = prog.statements[0].body[0].value
    assert isinstance(val, FunctionCallNode)
    assert val.name == "env"
    assert len(val.args) == 2


# ----------------------------------------------------------------- macro def
def test_macro_definition():
    src = 'macro SET(a, b) { server.host = a; server.port = b; }'
    prog, bag = parse(src)
    assert not bag.has_errors
    node = prog.statements[0]
    assert isinstance(node, MacroDefinitionNode)
    assert node.name == "SET"
    assert node.parameters == ["a", "b"]
    assert len(node.body) == 2


# ----------------------------------------------------------------- macro call
def test_macro_call():
    src = 'SET_SERVER("localhost", 8080);'
    prog, bag = parse(src)
    assert not bag.has_errors
    node = prog.statements[0]
    assert isinstance(node, MacroCallNode)
    assert node.name == "SET_SERVER"
    assert len(node.arguments) == 2


# ----------------------------------------------------------------- script
def test_script_block():
    src = 'script start { print "hello"; run "app"; }'
    prog, bag = parse(src)
    assert not bag.has_errors
    node = prog.statements[0]
    assert isinstance(node, ScriptNode)
    assert node.name == "start"
    assert len(node.body) == 2


# ----------------------------------------------------------------- errors
def test_missing_semicolon():
    prog, bag = parse('[s] { x = 1 }')
    assert bag.has_errors


def test_unclosed_brace():
    prog, bag = parse('[s] { x = 1;')
    assert bag.has_errors


def test_malformed_macro_definition():
    prog, bag = parse('macro { }')
    assert bag.has_errors
