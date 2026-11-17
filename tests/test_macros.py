"""Tests for the macro processor."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.macro.processor import MacroProcessor
from mecsl.parser.ast import AssignmentNode, LiteralNode, MacroCallNode


def process(src: str):
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    prog = Parser(tokens, "<test>", bag).parse()
    mp = MacroProcessor(bag)
    mp.collect_definitions(prog)
    expanded = mp.expand_program(prog)
    return expanded, bag


# ----------------------------------------------------------------- basic expansion
def test_one_arg_macro():
    src = """
macro SET_HOST(h) { server.host = h; }
SET_HOST("localhost");
"""
    expanded, bag = process(src)
    assert not bag.has_errors
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    assert len(assigns) == 1
    assert assigns[0].target_qualified == "server.host"
    assert assigns[0].value.value == "localhost"


def test_two_arg_macro():
    src = """
macro SET(a, b) { server.host = a; server.port = b; }
SET("myhost", 9000);
"""
    expanded, bag = process(src)
    assert not bag.has_errors
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    assert len(assigns) == 2
    assert assigns[0].value.value == "myhost"
    assert assigns[1].value.value == 9000


def test_multiple_macro_calls():
    src = """
macro SET_KEY(k, v) { cfg.k = v; }
SET_KEY("a", 1);
SET_KEY("b", 2);
"""
    expanded, bag = process(src)
    assert not bag.has_errors
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    assert len(assigns) == 2


def test_integer_arg():
    src = """
macro SET_PORT(p) { server.port = p; }
SET_PORT(8080);
"""
    expanded, bag = process(src)
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    assert assigns[0].value.value == 8080


def test_boolean_arg():
    src = """
macro SET_FLAG(f) { cfg.flag = f; }
SET_FLAG(true);
"""
    expanded, bag = process(src)
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    assert assigns[0].value.value is True


# ----------------------------------------------------------------- errors
def test_undefined_macro():
    src = "UNDEFINED_MACRO(1);"
    expanded, bag = process(src)
    assert bag.has_errors
    codes = [d.code for d in bag.items]
    assert "E301" in codes


def test_wrong_arg_count():
    src = """
macro M(a) { x = a; }
M(1, 2);
"""
    expanded, bag = process(src)
    assert bag.has_errors
    codes = [d.code for d in bag.items]
    assert "E302" in codes


def test_recursive_macro_rejected():
    src = """
macro RECURSE(x) { RECURSE(x); }
RECURSE(1);
"""
    expanded, bag = process(src)
    assert bag.has_errors
    codes = [d.code for d in bag.items]
    assert "E303" in codes


def test_duplicate_macro_rejected():
    src = """
macro M(a) { x = a; }
macro M(b) { y = b; }
"""
    expanded, bag = process(src)
    assert bag.has_errors


# ----------------------------------------------------------------- no raw string replacement
def test_macro_definitions_removed_from_stream():
    src = """
macro SET(a) { x = a; }
SET(42);
"""
    expanded, bag = process(src)
    from mecsl.parser.ast import MacroDefinitionNode
    defs = [s for s in expanded.statements if isinstance(s, MacroDefinitionNode)]
    assert len(defs) == 0


def test_list_arg():
    src = """
macro SET_LIST(l) { cfg.items = l; }
SET_LIST(["a", "b"]);
"""
    expanded, bag = process(src)
    assigns = [s for s in expanded.statements if isinstance(s, AssignmentNode)]
    from mecsl.parser.ast import ListNode
    assert isinstance(assigns[0].value, ListNode)
