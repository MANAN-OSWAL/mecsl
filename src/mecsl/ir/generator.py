"""IR generator: walks a macro-expanded AST and emits Instruction objects."""

from __future__ import annotations

import os
from typing import Any

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import UNKNOWN_SPAN
from mecsl.parser.ast import (
    ProgramNode, ImportNode, SectionNode, AssignmentNode,
    ScriptNode, PrintNode, RunNode,
    LiteralNode, ReferenceNode, IdentifierNode, FunctionCallNode, ListNode,
    ValueNode,
)
from mecsl.ir.instruction import Instruction, Opcode, LinkedModule


class IRGenerator:
    """Generates a list of Instructions from a ProgramNode."""

    def __init__(self, module_name: str, bag: DiagnosticBag) -> None:
        self._module = module_name
        self._bag = bag

    # ------------------------------------------------------------------ public
    def generate(self, program: ProgramNode) -> list[Instruction]:
        instructions: list[Instruction] = []
        instructions.append(Instruction(
            Opcode.MODULE_BEGIN, [self._module],
            module=self._module,
            source_span=program.source_span,
        ))

        for stmt in program.statements:
            instructions.extend(self._emit_stmt(stmt))

        instructions.append(Instruction(
            Opcode.MODULE_END, [self._module],
            module=self._module,
            source_span=program.source_span,
        ))
        return instructions

    # ----------------------------------------------------------------- private
    def _emit_stmt(self, stmt) -> list[Instruction]:
        if isinstance(stmt, ImportNode):
            return [Instruction(
                Opcode.IMPORT_MODULE, [stmt.path],
                module=self._module,
                source_span=stmt.source_span,
            )]
        if isinstance(stmt, SectionNode):
            return self._emit_section(stmt)
        if isinstance(stmt, AssignmentNode):
            return self._emit_assignment(stmt, section=None)
        if isinstance(stmt, ScriptNode):
            return self._emit_script(stmt)
        return []

    def _emit_section(self, node: SectionNode) -> list[Instruction]:
        result = [Instruction(
            Opcode.SECTION_BEGIN, [node.name],
            module=self._module, source_span=node.source_span,
        )]
        for assign in node.body:
            result.extend(self._emit_assignment(assign, section=node.name))
        result.append(Instruction(
            Opcode.SECTION_END, [node.name],
            module=self._module, source_span=node.source_span,
        ))
        return result

    def _emit_assignment(
        self, node: AssignmentNode, section: str | None
    ) -> list[Instruction]:
        if section:
            qname = f"{section}.{node.target_qualified}"
        else:
            qname = node.target_qualified

        value_node = node.value

        if isinstance(value_node, ReferenceNode):
            return [Instruction(
                Opcode.REFERENCE_VALUE,
                [qname, value_node.qualified_name],
                module=self._module, source_span=node.source_span,
            ), Instruction(
                Opcode.EXPORT_SYMBOL, [qname],
                module=self._module, source_span=node.source_span,
            )]

        typ, raw = self._value_type_and_raw(value_node)
        return [
            Instruction(
                Opcode.SET_VALUE, [qname, typ, raw],
                module=self._module, source_span=node.source_span,
            ),
            Instruction(
                Opcode.EXPORT_SYMBOL, [qname],
                module=self._module, source_span=node.source_span,
            ),
        ]

    def _emit_script(self, node: ScriptNode) -> list[Instruction]:
        cmds = []
        for cmd in node.body:
            if isinstance(cmd, PrintNode):
                _, raw = self._value_type_and_raw(cmd.value)
                cmds.append(Instruction(
                    Opcode.PRINT_VALUE, [str(raw)],
                    module=self._module, source_span=cmd.source_span,
                ))
            elif isinstance(cmd, RunNode):
                _, raw = self._value_type_and_raw(cmd.command)
                cmds.append(Instruction(
                    Opcode.DRY_RUN_COMMAND, [str(raw)],
                    module=self._module, source_span=cmd.source_span,
                ))
        result = [Instruction(
            Opcode.DEFINE_SCRIPT, [node.name],
            module=self._module, source_span=node.source_span,
        )]
        result.extend(cmds)
        return result

    @staticmethod
    def _value_type_and_raw(node: ValueNode) -> tuple[str, Any]:
        if isinstance(node, LiteralNode):
            if isinstance(node.value, bool):
                return ("BOOLEAN", node.value)
            if isinstance(node.value, int):
                return ("INTEGER", node.value)
            if isinstance(node.value, str):
                return ("STRING", node.value)
        if isinstance(node, ListNode):
            return ("LIST", [IRGenerator._value_type_and_raw(e)[1]
                             for e in node.elements])
        if isinstance(node, FunctionCallNode) and node.name == "env":
            var = node.args[0].value if node.args else ""
            default = node.args[1].value if len(node.args) > 1 else None
            return ("ENV", {"var": var, "default": default})
        if isinstance(node, ReferenceNode):
            return ("REFERENCE", node.qualified_name)
        if isinstance(node, IdentifierNode):
            return ("REFERENCE", node.name)
        return ("UNKNOWN", None)
