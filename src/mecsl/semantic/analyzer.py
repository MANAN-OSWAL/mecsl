"""Semantic analysis for MECSL.

Validates the macro-expanded AST against the merged symbol table.
Reports: undefined references, type errors, duplicate definitions,
env argument counts, run string requirement, unique script names.
"""

from __future__ import annotations

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import UNKNOWN_SPAN
from mecsl.parser.ast import (
    ProgramNode, ImportNode, SectionNode, AssignmentNode,
    ScriptNode, PrintNode, RunNode, MacroCallNode,
    LiteralNode, ReferenceNode, IdentifierNode, FunctionCallNode,
    ListNode, ValueNode,
)
from mecsl.symbols.tables import SymbolTable, SymbolKind


class SemanticAnalyzer:
    """Validates a macro-expanded ProgramNode against a merged SymbolTable."""

    def __init__(self, table: SymbolTable, bag: DiagnosticBag) -> None:
        self._table = table
        self._bag = bag
        self._script_names: set[str] = set()

    # ------------------------------------------------------------------ public
    def analyze(self, program: ProgramNode) -> None:
        for stmt in program.statements:
            self._check_stmt(stmt)

    # ----------------------------------------------------------------- private
    def _check_stmt(self, stmt) -> None:
        if isinstance(stmt, ImportNode):
            pass  # resolved by linker
        elif isinstance(stmt, SectionNode):
            for assign in stmt.body:
                self._check_assignment(assign)
        elif isinstance(stmt, AssignmentNode):
            self._check_assignment(stmt)
        elif isinstance(stmt, ScriptNode):
            self._check_script(stmt)
        elif isinstance(stmt, MacroCallNode):
            # All calls should already be expanded; any remaining = error
            self._bag.error(
                "E301",
                f"Unexpanded macro call '{stmt.name}' found during semantic analysis.",
                stmt.source_span,
            )

    def _check_assignment(self, node: AssignmentNode) -> None:
        self._check_value(node.value)

    def _check_value(self, node: ValueNode) -> None:
        if isinstance(node, LiteralNode):
            if node.value is None:
                self._bag.error(
                    "E201",
                    "Null literal value is not allowed.",
                    node.source_span,
                )
        elif isinstance(node, ReferenceNode):
            self._check_reference(node)
        elif isinstance(node, IdentifierNode):
            # Bare identifier used as value — treat as reference
            sym = self._table.lookup(node.name)
            if sym is None:
                self._bag.error(
                    "E203",
                    f"Undefined reference '{node.name}'.",
                    node.source_span,
                    suggestion=f"Define '{node.name}' before referencing it.",
                )
        elif isinstance(node, FunctionCallNode):
            self._check_function_call(node)
        elif isinstance(node, ListNode):
            for elem in node.elements:
                self._check_value(elem)

    def _check_reference(self, node: ReferenceNode) -> None:
        qname = node.qualified_name
        sym = self._table.lookup(qname)
        if sym is None:
            self._bag.error(
                "E203",
                f"Undefined reference '{qname}'.",
                node.source_span,
                suggestion=f"Ensure '{qname}' is defined in an imported or current file.",
            )

    def _check_function_call(self, node: FunctionCallNode) -> None:
        if node.name == "env":
            if not (1 <= len(node.args) <= 2):
                self._bag.error(
                    "E302",
                    f"'env' requires 1 or 2 arguments, got {len(node.args)}.",
                    node.source_span,
                    suggestion="Use env(\"VAR_NAME\") or env(\"VAR_NAME\", default).",
                )
            else:
                # First arg must be a string
                first = node.args[0]
                if not (isinstance(first, LiteralNode) and isinstance(first.value, str)):
                    self._bag.error(
                        "E201",
                        "First argument to 'env' must be a string literal.",
                        node.source_span,
                    )
        else:
            self._bag.error(
                "E201",
                f"Unknown built-in function '{node.name}'.",
                node.source_span,
            )

    def _check_script(self, node: ScriptNode) -> None:
        if node.name in self._script_names:
            self._bag.error(
                "E204",
                f"Duplicate script name '{node.name}'.",
                node.source_span,
                suggestion="Use a unique name for each script block.",
            )
        else:
            self._script_names.add(node.name)

        for cmd in node.body:
            if isinstance(cmd, RunNode):
                if not (isinstance(cmd.command, LiteralNode)
                        and isinstance(cmd.command.value, str)):
                    self._bag.error(
                        "E601",
                        "'run' command requires a string literal argument.",
                        cmd.source_span,
                    )
            elif isinstance(cmd, PrintNode):
                self._check_value(cmd.value)
