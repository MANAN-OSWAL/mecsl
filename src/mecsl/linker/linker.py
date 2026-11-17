"""Static linker for MECSL.

Resolves the import graph, merges per-module IR into a single LinkedModule,
builds an export table, and reports unresolved symbols.

Design decision: the linker operates on in-memory IR rather than writing
object files. A LinkedModule data structure makes the linker phase visible
in the architecture.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import UNKNOWN_SPAN, SourceSpan
from mecsl.ir.instruction import Instruction, Opcode, LinkedModule


class Linker:
    """Merges multiple IR module instruction lists into one LinkedModule."""

    def __init__(self, bag: DiagnosticBag) -> None:
        self._bag = bag

    # ------------------------------------------------------------------ public
    def link(
        self,
        modules: dict[str, list[Instruction]],
        entry_module: str,
    ) -> LinkedModule:
        """
        Parameters
        ----------
        modules : { module_name -> instructions }
        entry_module : name of the main (entry) module
        """
        # Resolve import order via topological sort
        order = self._resolve_order(modules, entry_module)

        merged: list[Instruction] = []
        export_table: dict[str, Any] = {}
        seen_exports: dict[str, str] = {}  # qname -> module

        for mod_name in order:
            instrs = modules.get(mod_name, [])
            for instr in instrs:
                merged.append(instr)
                if instr.opcode == Opcode.EXPORT_SYMBOL:
                    qname = instr.operands[0]
                    if qname in seen_exports:
                        self._bag.error(
                            "E204",
                            f"Duplicate exported symbol '{qname}' "
                            f"from modules '{seen_exports[qname]}' and '{mod_name}'.",
                            instr.source_span,
                        )
                    else:
                        seen_exports[qname] = mod_name
                        export_table[qname] = None  # value filled by loader

        # Check that all REFERENCE_VALUE operands resolve
        for instr in merged:
            if instr.opcode == Opcode.REFERENCE_VALUE:
                ref_target = instr.operands[1]
                if ref_target not in seen_exports:
                    self._bag.error(
                        "E203",
                        f"Unresolved symbol reference '{ref_target}'.",
                        instr.source_span,
                        suggestion=f"Define '{ref_target}' in an imported module.",
                    )

        return LinkedModule(
            name=entry_module,
            instructions=merged,
            export_table=export_table,
        )

    # ----------------------------------------------------------------- private
    def _resolve_order(
        self,
        modules: dict[str, list[Instruction]],
        entry: str,
    ) -> list[str]:
        """Return modules in dependency-first order (topological sort)."""
        visited: set[str] = set()
        order: list[str] = []
        in_stack: set[str] = set()

        def visit(name: str, import_span: SourceSpan = UNKNOWN_SPAN) -> None:
            if name in in_stack:
                self._bag.error(
                    "E402",
                    f"Import cycle detected involving module '{name}'.",
                    import_span,
                )
                return
            if name in visited:
                return
            if name not in modules:
                self._bag.error(
                    "E401",
                    f"Module '{name}' not found.",
                    import_span,
                    suggestion=f"Ensure '{name}' is compiled before linking.",
                )
                return
            in_stack.add(name)
            # Find IMPORT_MODULE instructions for this module
            for instr in modules[name]:
                if instr.opcode == Opcode.IMPORT_MODULE:
                    imported = instr.operands[0]
                    # Normalize: strip path and extension for module lookup
                    imported_name = Path(imported).stem
                    visit(imported_name, instr.source_span)
            in_stack.remove(name)
            visited.add(name)
            order.append(name)

        visit(entry)
        return order
