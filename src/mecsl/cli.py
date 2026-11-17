"""Command-line interface for MECSL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mecsl.diagnostics import DiagnosticError
from mecsl.pipeline import Pipeline
from mecsl.ir.instruction import Opcode


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mecsl",
        description="MECSL — Macro-Enabled Configuration and Scripting Language",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # tokens
    t = sub.add_parser("tokens", help="Print tokens for a source file.")
    t.add_argument("file", help="Path to .mecs source file.")

    # check
    c = sub.add_parser("check", help="Validate a source file.")
    c.add_argument("file")

    # expand
    e = sub.add_parser("expand", help="Print macro-expanded AST representation.")
    e.add_argument("file")

    # symbols
    s = sub.add_parser("symbols", help="Print symbol table entries.")
    s.add_argument("file")

    # ir
    i = sub.add_parser("ir", help="Print generated IR instructions.")
    i.add_argument("file")

    # build
    b = sub.add_parser("build", help="Link, load, and write JSON output.")
    b.add_argument("file")
    b.add_argument("--output", "-o", default="build/output.json",
                   help="Output JSON file path.")

    # run
    r = sub.add_parser("run", help="Execute script blocks (dry-run by default).")
    r.add_argument("file")
    r.add_argument("--dry-run", action="store_true", default=True,
                   help="Show script plan without executing (default: True).")

    return p


def cmd_tokens(args: argparse.Namespace) -> int:
    from mecsl.diagnostics import DiagnosticBag
    from mecsl.lexer.lexer import Lexer
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    bag = DiagnosticBag()
    src = path.read_text(encoding="utf-8")
    lexer = Lexer(src, str(path), bag)
    tokens = lexer.tokenize()
    for tok in tokens:
        sp = tok.source_span
        print(f"{tok.kind.name:<12} {tok.lexeme!r:<30} "
              f"{sp.file}:{sp.start_line}:{sp.start_column}")
    _print_diagnostics(bag)
    return 1 if bag.has_errors else 0


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        pipe.run()
        diags = pipe.bag.items
        if diags:
            _print_diagnostics(pipe.bag)
            return 1
        print("OK — no errors found.")
        return 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


def cmd_expand(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        expanded = pipe.get_expanded()
        _print_expanded(expanded)
        _print_diagnostics(pipe.bag)
        return 1 if pipe.bag.has_errors else 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


def cmd_symbols(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        table = pipe.get_merged_symbol_table()
        print(table.dump())
        _print_diagnostics(pipe.bag)
        return 1 if pipe.bag.has_errors else 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


def cmd_ir(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        instructions = pipe.get_ir()
        for instr in instructions:
            print(instr)
        _print_diagnostics(pipe.bag)
        return 1 if pipe.bag.has_errors else 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


def cmd_build(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        result = pipe.run()
        from mecsl.loader.loader import Loader
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        json_str = Loader.to_json(result)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Built: {out_path}")
        print(json_str)
        _print_diagnostics(pipe.bag)
        return 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    pipe = Pipeline(str(path))
    try:
        instructions = pipe.get_ir()
        current_script = None
        for instr in instructions:
            if instr.opcode == Opcode.DEFINE_SCRIPT:
                current_script = instr.operands[0]
                print(f"\n--- Script: {current_script} ---")
            elif instr.opcode == Opcode.PRINT_VALUE:
                print(f"  PRINT: {instr.operands[0]}")
            elif instr.opcode == Opcode.DRY_RUN_COMMAND:
                print(f"  [DRY-RUN] Would execute: {instr.operands[0]!r}")
        _print_diagnostics(pipe.bag)
        return 1 if pipe.bag.has_errors else 0
    except DiagnosticError:
        _print_diagnostics(pipe.bag)
        return 1


# ------------------------------------------------------------------ helpers
def _print_diagnostics(bag) -> None:
    for d in bag.items:
        print(str(d), file=sys.stderr)


def _print_expanded(program) -> None:
    """Simple readable dump of the expanded AST."""
    from mecsl.parser.ast import (
        ImportNode, SectionNode, AssignmentNode, ScriptNode,
        MacroCallNode, PrintNode, RunNode,
        LiteralNode, ReferenceNode, IdentifierNode, FunctionCallNode, ListNode,
    )

    def fmt_val(v) -> str:
        if isinstance(v, LiteralNode):
            return repr(v.value)
        if isinstance(v, ReferenceNode):
            return v.qualified_name
        if isinstance(v, IdentifierNode):
            return v.name
        if isinstance(v, ListNode):
            return "[" + ", ".join(fmt_val(e) for e in v.elements) + "]"
        if isinstance(v, FunctionCallNode):
            args = ", ".join(fmt_val(a) for a in v.args)
            return f"{v.name}({args})"
        return str(v)

    print(f"# Expanded: {program.source_file}")
    for stmt in program.statements:
        if isinstance(stmt, ImportNode):
            print(f'import "{stmt.path}";')
        elif isinstance(stmt, SectionNode):
            print(f"[{stmt.name}] {{")
            for a in stmt.body:
                print(f"    {a.target_qualified} = {fmt_val(a.value)};")
            print("}")
        elif isinstance(stmt, AssignmentNode):
            print(f"{stmt.target_qualified} = {fmt_val(stmt.value)};")
        elif isinstance(stmt, ScriptNode):
            print(f"script {stmt.name} {{")
            for cmd in stmt.body:
                if isinstance(cmd, PrintNode):
                    print(f"    print {fmt_val(cmd.value)};")
                elif isinstance(cmd, RunNode):
                    print(f"    run {fmt_val(cmd.command)};")
            print("}")
        elif isinstance(stmt, MacroCallNode):
            args = ", ".join(fmt_val(a) for a in stmt.arguments)
            print(f"{stmt.name}({args});")


# ------------------------------------------------------------------ entry
def main(argv: list[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "tokens":  cmd_tokens,
        "check":   cmd_check,
        "expand":  cmd_expand,
        "symbols": cmd_symbols,
        "ir":      cmd_ir,
        "build":   cmd_build,
        "run":     cmd_run,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))
