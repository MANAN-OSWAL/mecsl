"""AST-based macro processor for MECSL.

Design decision: macros are expanded via deep-copy + parameter substitution
on the AST, never via string replacement. This preserves source locations and
types across expansion.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import SourceSpan, UNKNOWN_SPAN
from mecsl.parser.ast import (
    ProgramNode, MacroDefinitionNode, MacroCallNode,
    AssignmentNode, SectionNode, ScriptNode, ImportNode,
    PrintNode, RunNode, IdentifierNode, LiteralNode, ListNode,
    ReferenceNode, FunctionCallNode,
    StatementNode, ValueNode,
)

_MAX_DEPTH = 32  # configurable recursion limit


@dataclass
class MacroDefinition:
    name: str
    parameters: list[str]
    body: list[StatementNode]
    source_span: SourceSpan = field(default=UNKNOWN_SPAN)


class MacroProcessor:
    """Collects macro definitions and expands all macro calls in a ProgramNode."""

    def __init__(self, bag: DiagnosticBag) -> None:
        self._bag = bag
        self._defs: dict[str, MacroDefinition] = {}

    # ------------------------------------------------------------------ public
    def collect_definitions(self, program: ProgramNode) -> None:
        """First pass: register all MacroDefinitionNode instances."""
        for stmt in program.statements:
            if isinstance(stmt, MacroDefinitionNode):
                if stmt.name in self._defs:
                    self._bag.error(
                        "E204",
                        f"Duplicate macro definition: '{stmt.name}'.",
                        stmt.source_span,
                        suggestion="Rename or remove the duplicate macro.",
                    )
                else:
                    self._defs[stmt.name] = MacroDefinition(
                        name=stmt.name,
                        parameters=list(stmt.parameters),
                        body=list(stmt.body),
                        source_span=stmt.source_span,
                    )

    def expand_program(self, program: ProgramNode) -> ProgramNode:
        """Return a new ProgramNode with macro defs removed and calls expanded."""
        new_stmts: list[StatementNode] = []
        for stmt in program.statements:
            if isinstance(stmt, MacroDefinitionNode):
                continue  # strip definition from executable stream
            elif isinstance(stmt, MacroCallNode):
                expanded = self.expand_call(stmt)
                new_stmts.extend(expanded)
            elif isinstance(stmt, SectionNode):
                new_stmts.append(self._expand_section(stmt))
            else:
                new_stmts.append(stmt)
        return ProgramNode(
            source_span=program.source_span,
            statements=new_stmts,
            source_file=program.source_file,
        )

    def expand_call(
        self, call: MacroCallNode, depth: int = 0
    ) -> list[StatementNode]:
        """Expand a single macro call into a list of statements."""
        if depth > _MAX_DEPTH:
            self._bag.error(
                "E303",
                f"Recursive macro expansion exceeded depth {_MAX_DEPTH} "
                f"while expanding '{call.name}'.",
                call.source_span,
            )
            return []

        defn = self._defs.get(call.name)
        if defn is None:
            self._bag.error(
                "E301",
                f"Undefined macro '{call.name}'.",
                call.source_span,
                suggestion="Define the macro before calling it.",
            )
            return []

        if len(call.arguments) != len(defn.parameters):
            self._bag.error(
                "E302",
                f"Macro '{call.name}' expects {len(defn.parameters)} argument(s) "
                f"but got {len(call.arguments)}.",
                call.source_span,
            )
            return []

        bindings: dict[str, ValueNode] = {
            param: arg
            for param, arg in zip(defn.parameters, call.arguments)
        }

        result: list[StatementNode] = []
        for stmt in defn.body:
            expanded_stmt = self._substitute_stmt(
                copy.deepcopy(stmt), bindings, depth
            )
            if isinstance(expanded_stmt, list):
                result.extend(expanded_stmt)
            elif expanded_stmt is not None:
                result.append(expanded_stmt)
        return result

    # ----------------------------------------------------------------- private
    def _expand_section(self, section: SectionNode) -> SectionNode:
        """Expand any macro calls that somehow ended up inside a section body."""
        new_body = []
        for stmt in section.body:
            if isinstance(stmt, AssignmentNode):
                new_body.append(stmt)
            elif isinstance(stmt, MacroCallNode):
                new_body.extend(self.expand_call(stmt))
        return SectionNode(
            source_span=section.source_span,
            name=section.name,
            body=new_body,
        )

    def _substitute_stmt(
        self,
        stmt: StatementNode,
        bindings: dict[str, ValueNode],
        depth: int,
    ) -> StatementNode | list[StatementNode] | None:
        if isinstance(stmt, AssignmentNode):
            stmt.value = self._substitute_value(stmt.value, bindings)
            return stmt
        if isinstance(stmt, MacroCallNode):
            # Substitute args first, then expand
            new_args = [self._substitute_value(a, bindings) for a in stmt.arguments]
            new_call = MacroCallNode(
                source_span=stmt.source_span,
                name=stmt.name,
                arguments=new_args,
            )
            return self.expand_call(new_call, depth + 1)
        if isinstance(stmt, PrintNode):
            stmt.value = self._substitute_value(stmt.value, bindings)
            return stmt
        if isinstance(stmt, RunNode):
            stmt.command = self._substitute_value(stmt.command, bindings)
            return stmt
        return stmt

    def _substitute_value(
        self,
        node: ValueNode,
        bindings: dict[str, ValueNode],
    ) -> ValueNode:
        if isinstance(node, IdentifierNode):
            if node.name in bindings:
                return copy.deepcopy(bindings[node.name])
            # Plain identifier stays as-is (becomes a reference at semantic check)
            return node
        if isinstance(node, ReferenceNode):
            # If the first part matches a binding, substitute
            if node.parts[0] in bindings and len(node.parts) == 1:
                return copy.deepcopy(bindings[node.parts[0]])
            return node
        if isinstance(node, ListNode):
            node.elements = [
                self._substitute_value(e, bindings) for e in node.elements
            ]
            return node
        if isinstance(node, FunctionCallNode):
            node.args = [
                self._substitute_value(a, bindings) for a in node.args
            ]
            return node
        # LiteralNode — no substitution needed
        return node
