"""Tests for IR generation."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.macro.processor import MacroProcessor
from mecsl.ir.generator import IRGenerator
from mecsl.ir.instruction import Opcode


def gen_ir(src: str):
    bag = DiagnosticBag()
    tokens = Lexer(src, "<test>", bag).tokenize()
    prog = Parser(tokens, "<test>", bag).parse()
    mp = MacroProcessor(bag)
    mp.collect_definitions(prog)
    expanded = mp.expand_program(prog)
    gen = IRGenerator("test", bag)
    instructions = gen.generate(expanded)
    return instructions, bag


def opcodes(instructions):
    return [i.opcode for i in instructions]


def test_module_begin_end():
    instrs, _ = gen_ir("")
    assert instrs[0].opcode == Opcode.MODULE_BEGIN
    assert instrs[-1].opcode == Opcode.MODULE_END


def test_section_begin_end():
    instrs, bag = gen_ir('[s] { x = 1; }')
    assert not bag.has_errors
    ops = opcodes(instrs)
    assert Opcode.SECTION_BEGIN in ops
    assert Opcode.SECTION_END in ops


def test_set_value_string():
    instrs, bag = gen_ir('[s] { host = "localhost"; }')
    set_instrs = [i for i in instrs if i.opcode == Opcode.SET_VALUE]
    assert len(set_instrs) == 1
    qname, typ, val = set_instrs[0].operands
    assert qname == "s.host"
    assert typ == "STRING"
    assert val == "localhost"


def test_set_value_integer():
    instrs, _ = gen_ir('[s] { port = 8080; }')
    set_i = [i for i in instrs if i.opcode == Opcode.SET_VALUE][0]
    assert set_i.operands[1] == "INTEGER"
    assert set_i.operands[2] == 8080


def test_set_value_boolean():
    instrs, _ = gen_ir('[s] { flag = true; }')
    set_i = [i for i in instrs if i.opcode == Opcode.SET_VALUE][0]
    assert set_i.operands[1] == "BOOLEAN"
    assert set_i.operands[2] is True


def test_reference_value():
    instrs, _ = gen_ir('[a] { x = b.y; }')
    ref_instrs = [i for i in instrs if i.opcode == Opcode.REFERENCE_VALUE]
    assert len(ref_instrs) == 1
    assert ref_instrs[0].operands[1] == "b.y"


def test_script_dry_run():
    instrs, _ = gen_ir('script s { print "hi"; run "app"; }')
    ops = opcodes(instrs)
    assert Opcode.DEFINE_SCRIPT in ops
    assert Opcode.PRINT_VALUE in ops
    assert Opcode.DRY_RUN_COMMAND in ops


def test_export_symbol_generated():
    instrs, _ = gen_ir('[s] { x = 1; }')
    exports = [i for i in instrs if i.opcode == Opcode.EXPORT_SYMBOL]
    assert len(exports) >= 1
