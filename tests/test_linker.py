"""Tests for the linker."""

import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.ir.instruction import Instruction, Opcode, LinkedModule
from mecsl.linker.linker import Linker
from mecsl.source import UNKNOWN_SPAN


def make_instr(opcode: Opcode, *operands) -> Instruction:
    return Instruction(opcode=opcode, operands=list(operands),
                       module="test", source_span=UNKNOWN_SPAN)


def test_single_module_link():
    bag = DiagnosticBag()
    modules = {
        "main": [
            make_instr(Opcode.MODULE_BEGIN, "main"),
            make_instr(Opcode.SET_VALUE, "s.x", "INTEGER", 1),
            make_instr(Opcode.EXPORT_SYMBOL, "s.x"),
            make_instr(Opcode.MODULE_END, "main"),
        ]
    }
    linker = Linker(bag)
    linked = linker.link(modules, "main")
    assert not bag.has_errors
    assert isinstance(linked, LinkedModule)
    assert "s.x" in linked.export_table


def test_two_modules_linked():
    bag = DiagnosticBag()
    modules = {
        "common": [
            make_instr(Opcode.MODULE_BEGIN, "common"),
            make_instr(Opcode.SET_VALUE, "cfg.x", "STRING", "hello"),
            make_instr(Opcode.EXPORT_SYMBOL, "cfg.x"),
            make_instr(Opcode.MODULE_END, "common"),
        ],
        "main": [
            make_instr(Opcode.MODULE_BEGIN, "main"),
            make_instr(Opcode.IMPORT_MODULE, "common"),
            make_instr(Opcode.REFERENCE_VALUE, "app.host", "cfg.x"),
            make_instr(Opcode.EXPORT_SYMBOL, "app.host"),
            make_instr(Opcode.MODULE_END, "main"),
        ],
    }
    linker = Linker(bag)
    linked = linker.link(modules, "main")
    assert not bag.has_errors
    assert "cfg.x" in linked.export_table
    assert "app.host" in linked.export_table


def test_unresolved_reference_reported():
    bag = DiagnosticBag()
    modules = {
        "main": [
            make_instr(Opcode.MODULE_BEGIN, "main"),
            make_instr(Opcode.REFERENCE_VALUE, "app.host", "missing.key"),
            make_instr(Opcode.EXPORT_SYMBOL, "app.host"),
            make_instr(Opcode.MODULE_END, "main"),
        ]
    }
    linker = Linker(bag)
    linker.link(modules, "main")
    assert bag.has_errors
    assert any(d.code == "E203" for d in bag.items)


def test_duplicate_export_reported():
    bag = DiagnosticBag()
    modules = {
        "main": [
            make_instr(Opcode.MODULE_BEGIN, "main"),
            make_instr(Opcode.SET_VALUE, "s.x", "INTEGER", 1),
            make_instr(Opcode.EXPORT_SYMBOL, "s.x"),
            make_instr(Opcode.SET_VALUE, "s.x", "INTEGER", 2),
            make_instr(Opcode.EXPORT_SYMBOL, "s.x"),
            make_instr(Opcode.MODULE_END, "main"),
        ]
    }
    linker = Linker(bag)
    linker.link(modules, "main")
    assert bag.has_errors
