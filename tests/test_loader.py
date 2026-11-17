"""Tests for the loader."""

import os
import pytest
from mecsl.diagnostics import DiagnosticBag
from mecsl.ir.instruction import Instruction, Opcode, LinkedModule
from mecsl.loader.loader import Loader
from mecsl.source import UNKNOWN_SPAN


def make_instr(opcode: Opcode, *operands) -> Instruction:
    return Instruction(opcode=opcode, operands=list(operands),
                       module="test", source_span=UNKNOWN_SPAN)


def make_linked(*instrs) -> LinkedModule:
    return LinkedModule(name="test", instructions=list(instrs))


def test_simple_string_value():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "server.host", "STRING", "localhost"),
        make_instr(Opcode.EXPORT_SYMBOL, "server.host"),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["server"]["host"] == "localhost"


def test_integer_value():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "server.port", "INTEGER", 8080),
        make_instr(Opcode.EXPORT_SYMBOL, "server.port"),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["server"]["port"] == 8080


def test_boolean_value():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "cfg.flag", "BOOLEAN", True),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["cfg"]["flag"] is True


def test_env_with_default(monkeypatch):
    monkeypatch.delenv("TEST_VAR", raising=False)
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "s.val", "ENV",
                   {"var": "TEST_VAR", "default": "fallback"}),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["s"]["val"] == "fallback"


def test_env_from_environment(monkeypatch):
    monkeypatch.setenv("MY_PORT", "9000")
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "s.port", "ENV",
                   {"var": "MY_PORT", "default": 8080}),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["s"]["port"] == "9000"


def test_reference_resolved():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "server.host", "STRING", "remotehost"),
        make_instr(Opcode.EXPORT_SYMBOL, "server.host"),
        make_instr(Opcode.REFERENCE_VALUE, "app.host", "server.host"),
        make_instr(Opcode.EXPORT_SYMBOL, "app.host"),
    )
    result = Loader(bag).load(linked)
    assert result["config"]["app"]["host"] == "remotehost"


def test_script_stored_separately():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.DEFINE_SCRIPT, "start"),
        make_instr(Opcode.PRINT_VALUE, "Starting"),
        make_instr(Opcode.DRY_RUN_COMMAND, "myapp"),
    )
    result = Loader(bag).load(linked)
    assert "start" in result["scripts"]
    cmds = result["scripts"]["start"]
    assert cmds[0]["action"] == "print"
    assert cmds[1]["action"] == "dry_run"


def test_deterministic_output():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "z.b", "INTEGER", 2),
        make_instr(Opcode.SET_VALUE, "a.x", "INTEGER", 1),
    )
    result = Loader(bag).load(linked)
    keys = list(result["config"].keys())
    assert keys == sorted(keys)


def test_to_json():
    bag = DiagnosticBag()
    linked = make_linked(
        make_instr(Opcode.SET_VALUE, "s.x", "STRING", "hello"),
    )
    result = Loader(bag).load(linked)
    import json
    parsed = json.loads(Loader.to_json(result))
    assert parsed["s"]["x"] == "hello"
