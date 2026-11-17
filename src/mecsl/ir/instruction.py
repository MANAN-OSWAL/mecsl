"""IR instruction definitions for MECSL."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from mecsl.source import SourceSpan, UNKNOWN_SPAN


class Opcode(str, Enum):
    MODULE_BEGIN     = "MODULE_BEGIN"
    MODULE_END       = "MODULE_END"
    IMPORT_MODULE    = "IMPORT_MODULE"
    SECTION_BEGIN    = "SECTION_BEGIN"
    SECTION_END      = "SECTION_END"
    SET_VALUE        = "SET_VALUE"
    REFERENCE_VALUE  = "REFERENCE_VALUE"
    DEFINE_SCRIPT    = "DEFINE_SCRIPT"
    PRINT_VALUE      = "PRINT_VALUE"
    DRY_RUN_COMMAND  = "DRY_RUN_COMMAND"
    EXPORT_SYMBOL    = "EXPORT_SYMBOL"


@dataclass
class Instruction:
    opcode: Opcode
    operands: list[Any] = field(default_factory=list)
    module: str = ""
    source_span: SourceSpan = field(default=UNKNOWN_SPAN)

    def __str__(self) -> str:
        ops = " ".join(str(o) for o in self.operands)
        return f"{self.opcode.value:<20} {ops}".rstrip()


@dataclass
class LinkedModule:
    """The output of the linker: a single merged IR module."""
    name: str
    instructions: list[Instruction] = field(default_factory=list)
    export_table: dict[str, Any] = field(default_factory=dict)  # qname -> value
