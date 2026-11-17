"""Loader for MECSL.

Converts a LinkedModule's IR into a hierarchical Python dictionary,
evaluates env() calls, resolves cross-references, and stores script plans.
Output is serializable to JSON.
"""

from __future__ import annotations

import json
import os
from typing import Any

from mecsl.diagnostics import DiagnosticBag
from mecsl.ir.instruction import Instruction, Opcode, LinkedModule


class Loader:
    """Executes linked IR instructions to produce the final configuration dict."""

    def __init__(self, bag: DiagnosticBag) -> None:
        self._bag = bag

    # ------------------------------------------------------------------ public
    def load(self, linked: LinkedModule) -> dict[str, Any]:
        """
        Returns a dict with two top-level keys:
          "config"  -> hierarchical section/key dictionary
          "scripts" -> { script_name -> [cmd, ...] }
        """
        flat: dict[str, Any] = {}      # qname -> raw value (before reference resolve)
        scripts: dict[str, list[str]] = {}
        current_script: str | None = None

        # --- first pass: collect all SET_VALUE and REFERENCE_VALUE in order ---
        for instr in linked.instructions:
            op = instr.opcode

            if op == Opcode.SET_VALUE:
                qname, typ, raw = instr.operands
                flat[qname] = self._coerce(typ, raw)

            elif op == Opcode.REFERENCE_VALUE:
                qname, ref_target = instr.operands
                flat[qname] = ("__ref__", ref_target)

            elif op == Opcode.DEFINE_SCRIPT:
                current_script = instr.operands[0]
                scripts[current_script] = []

            elif op == Opcode.PRINT_VALUE:
                if current_script is not None:
                    scripts[current_script].append(
                        {"action": "print", "value": instr.operands[0]}
                    )

            elif op == Opcode.DRY_RUN_COMMAND:
                if current_script is not None:
                    scripts[current_script].append(
                        {"action": "dry_run", "command": instr.operands[0]}
                    )

        # --- second pass: resolve references ---
        for key, val in flat.items():
            if isinstance(val, tuple) and val[0] == "__ref__":
                target = val[1]
                resolved = flat.get(target)
                if resolved is None:
                    self._bag.error(
                        "E203",
                        f"Cannot resolve reference '{target}' for key '{key}'.",
                        # No span available at load time
                    )
                    flat[key] = None
                elif isinstance(resolved, tuple) and resolved[0] == "__ref__":
                    # Chain ref: resolve one level (deep chains not supported)
                    flat[key] = flat.get(resolved[1])
                else:
                    flat[key] = resolved

        # --- build hierarchical dict from dotted keys ---
        config = self._nest(flat)

        return {
            "config": config,
            "scripts": scripts,
        }

    # ----------------------------------------------------------------- private
    @staticmethod
    def _coerce(typ: str, raw: Any) -> Any:
        if typ == "STRING":
            return str(raw)
        if typ == "INTEGER":
            return int(raw)
        if typ == "BOOLEAN":
            return bool(raw)
        if typ == "LIST":
            return list(raw)
        if typ == "ENV":
            var = raw.get("var", "")
            default = raw.get("default")
            return os.environ.get(var, default)
        if typ == "REFERENCE":
            return ("__ref__", raw)
        return raw

    @staticmethod
    def _nest(flat: dict[str, Any]) -> dict[str, Any]:
        """Convert {"section.key": value} -> {"section": {"key": value}}."""
        result: dict[str, Any] = {}
        # Sort for deterministic output
        for qname in sorted(flat.keys()):
            val = flat[qname]
            parts = qname.split(".")
            node = result
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                if not isinstance(node[part], dict):
                    # Key collision — treat as nested anyway
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = val
        return result

    @staticmethod
    def to_json(output: dict[str, Any], indent: int = 2) -> str:
        return json.dumps(output["config"], indent=indent, sort_keys=True,
                          default=str)
