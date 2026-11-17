"""Symbol-table management for MECSL.

One SymbolTable is built per compilation unit (module). A global table merges
them during linking. Symbols are collected in a first pass so that references
can appear before definitions in the same linked program.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import SourceSpan, UNKNOWN_SPAN
from mecsl.parser.ast import (
    ProgramNode, ImportNode, MacroDefinitionNode, MacroCallNode,
    SectionNode, AssignmentNode, ScriptNode, LiteralNode,
    ReferenceNode, FunctionCallNode, IdentifierNode, ValueNode,
)


class SymbolKind(Enum):
    MODULE = auto()
    MACRO = auto()
    SECTION = auto()
    KEY = auto()
    EXTERNAL_REF = auto()
    SCRIPT = auto()


@dataclass
class Symbol:
    name: str
    qualified_name: str
    kind: SymbolKind
    type: str               # "string" | "integer" | "boolean" | "list" | "reference" | "env" | "unknown"
    module: str
    source_span: SourceSpan = field(default=UNKNOWN_SPAN)
    value: Any = None
    visibility: str = "public"   # "public" | "private"


class SymbolTable:
    """Holds all symbols for a single module."""

    def __init__(self, module_name: str, bag: DiagnosticBag) -> None:
        self.module_name = module_name
        self._bag = bag
        self._symbols: dict[str, Symbol] = {}  # qualified_name -> Symbol

    # ----------------------------------------------------------------- build
    def build_from_program(self, program: ProgramNode) -> None:
        """Walk an (already macro-expanded) ProgramNode and register symbols."""
        for stmt in program.statements:
            if isinstance(stmt, ImportNode):
                pass  # imports handled by linker
            elif isinstance(stmt, SectionNode):
                self._register_section(stmt)
            elif isinstance(stmt, AssignmentNode):
                self._register_assignment(stmt, section=None)
            elif isinstance(stmt, ScriptNode):
                self._register_script(stmt)
            elif isinstance(stmt, MacroDefinitionNode):
                self._register_macro(stmt)

    # ----------------------------------------------------------------- register
    def _register_section(self, node: SectionNode) -> None:
        qname = node.name
        self._add_symbol(Symbol(
            name=node.name,
            qualified_name=qname,
            kind=SymbolKind.SECTION,
            type="section",
            module=self.module_name,
            source_span=node.source_span,
        ))
        for assign in node.body:
            self._register_assignment(assign, section=node.name)

    def _register_assignment(
        self,
        node: AssignmentNode,
        section: Optional[str],
    ) -> None:
        if section:
            qname = f"{section}.{node.target_qualified}"
        else:
            qname = node.target_qualified

        typ = self._infer_type(node.value)
        self._add_symbol(Symbol(
            name=node.target[-1],
            qualified_name=qname,
            kind=SymbolKind.KEY,
            type=typ,
            module=self.module_name,
            source_span=node.source_span,
            value=node.value,
        ))

    def _register_macro(self, node: MacroDefinitionNode) -> None:
        self._add_symbol(Symbol(
            name=node.name,
            qualified_name=node.name,
            kind=SymbolKind.MACRO,
            type="macro",
            module=self.module_name,
            source_span=node.source_span,
        ))

    def _register_script(self, node: ScriptNode) -> None:
        self._add_symbol(Symbol(
            name=node.name,
            qualified_name=f"script:{node.name}",
            kind=SymbolKind.SCRIPT,
            type="script",
            module=self.module_name,
            source_span=node.source_span,
        ))

    def _add_symbol(self, sym: Symbol) -> None:
        if sym.qualified_name in self._symbols:
            existing = self._symbols[sym.qualified_name]
            # Allow section re-declaration only if merging from imports
            if sym.kind != SymbolKind.SECTION:
                self._bag.error(
                    "E204",
                    f"Duplicate definition of '{sym.qualified_name}' "
                    f"(first defined at {existing.source_span}).",
                    sym.source_span,
                    suggestion="Remove or rename the duplicate.",
                )
                return
        self._symbols[sym.qualified_name] = sym

    # ----------------------------------------------------------------- query
    def lookup(self, qualified_name: str) -> Optional[Symbol]:
        return self._symbols.get(qualified_name)

    def all_symbols(self) -> list[Symbol]:
        return sorted(self._symbols.values(), key=lambda s: s.qualified_name)

    def keys(self) -> list[Symbol]:
        return [s for s in self.all_symbols() if s.kind == SymbolKind.KEY]

    def merge(self, other: "SymbolTable") -> None:
        """Merge another module's symbols into this table (for linking)."""
        for sym in other.all_symbols():
            if sym.qualified_name not in self._symbols:
                self._symbols[sym.qualified_name] = sym
            else:
                existing = self._symbols[sym.qualified_name]
                if existing.module != sym.module:
                    self._bag.error(
                        "E204",
                        f"Conflicting definition of '{sym.qualified_name}' "
                        f"from modules '{existing.module}' and '{sym.module}'.",
                        sym.source_span,
                    )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _infer_type(node: ValueNode) -> str:
        if isinstance(node, LiteralNode):
            if isinstance(node.value, bool):
                return "boolean"
            if isinstance(node.value, int):
                return "integer"
            if isinstance(node.value, str):
                return "string"
            return "unknown"
        if isinstance(node, ReferenceNode):
            return "reference"
        if isinstance(node, FunctionCallNode):
            return node.name  # "env"
        from mecsl.parser.ast import ListNode
        if isinstance(node, ListNode):
            return "list"
        return "unknown"

    # ------------------------------------------------------------------ dump
    def dump(self) -> str:
        lines = [f"Symbol Table: module={self.module_name!r}",
                 f"{'QNAME':<40} {'KIND':<12} {'TYPE':<10} {'MODULE':<16}"]
        lines.append("-" * 80)
        for sym in self.all_symbols():
            lines.append(
                f"{sym.qualified_name:<40} {sym.kind.name:<12} "
                f"{sym.type:<10} {sym.module:<16}"
            )
        return "\n".join(lines)
