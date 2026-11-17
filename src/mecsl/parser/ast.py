"""AST node definitions for MECSL."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Union

from mecsl.source import SourceSpan, UNKNOWN_SPAN


# ─────────────────────────────────────── base
@dataclass
class Node:
    source_span: SourceSpan = field(default=UNKNOWN_SPAN, compare=False)

    def deep_copy(self) -> "Node":
        return copy.deepcopy(self)


# ─────────────────────────────────── value nodes
@dataclass
class LiteralNode(Node):
    """A literal value: string, integer, boolean."""
    value: Any = None  # str | int | bool


@dataclass
class IdentifierNode(Node):
    """A simple name — used for macro parameters, section names, etc."""
    name: str = ""


@dataclass
class ListNode(Node):
    """A list of value nodes  [ ... ]"""
    elements: list["ValueNode"] = field(default_factory=list)


@dataclass
class ReferenceNode(Node):
    """A qualified key reference like  server_defaults.host"""
    parts: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return ".".join(self.parts)


@dataclass
class FunctionCallNode(Node):
    """env("VAR", default)"""
    name: str = ""
    args: list["ValueNode"] = field(default_factory=list)


ValueNode = Union[LiteralNode, IdentifierNode, ListNode, ReferenceNode, FunctionCallNode]


# ─────────────────────────────── statement nodes
@dataclass
class ImportNode(Node):
    path: str = ""


@dataclass
class AssignmentNode(Node):
    """key = value  (target is a list of parts for qualified names)"""
    target: list[str] = field(default_factory=list)   # ["server", "host"]
    value: ValueNode = field(default_factory=lambda: LiteralNode(value=None))

    @property
    def target_qualified(self) -> str:
        return ".".join(self.target)


@dataclass
class SectionNode(Node):
    name: str = ""
    body: list[AssignmentNode] = field(default_factory=list)


@dataclass
class MacroDefinitionNode(Node):
    name: str = ""
    parameters: list[str] = field(default_factory=list)
    body: list["StatementNode"] = field(default_factory=list)


@dataclass
class MacroCallNode(Node):
    name: str = ""
    arguments: list[ValueNode] = field(default_factory=list)


@dataclass
class PrintNode(Node):
    value: ValueNode = field(default_factory=lambda: LiteralNode(value=""))


@dataclass
class RunNode(Node):
    command: ValueNode = field(default_factory=lambda: LiteralNode(value=""))


@dataclass
class ScriptNode(Node):
    name: str = ""
    body: list[Union[PrintNode, RunNode]] = field(default_factory=list)


StatementNode = Union[
    ImportNode,
    AssignmentNode,
    SectionNode,
    MacroDefinitionNode,
    MacroCallNode,
    ScriptNode,
]


# ─────────────────────────────────────── root
@dataclass
class ProgramNode(Node):
    statements: list[StatementNode] = field(default_factory=list)
    source_file: str = ""
