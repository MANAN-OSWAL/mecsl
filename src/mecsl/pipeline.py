"""Pipeline: orchestrates all phases of MECSL compilation.

This is the single entry point that glues together:
  import resolution -> lexing -> parsing -> macro expansion ->
  symbol table -> semantic analysis -> IR generation -> linking -> loading
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mecsl.diagnostics import DiagnosticBag, DiagnosticError
from mecsl.source import SourceSpan, UNKNOWN_SPAN
from mecsl.lexer.lexer import Lexer
from mecsl.parser.parser import Parser
from mecsl.parser.ast import ImportNode, ProgramNode
from mecsl.macro.processor import MacroProcessor
from mecsl.symbols.tables import SymbolTable
from mecsl.semantic.analyzer import SemanticAnalyzer
from mecsl.ir.generator import IRGenerator
from mecsl.ir.instruction import Instruction, LinkedModule
from mecsl.linker.linker import Linker
from mecsl.loader.loader import Loader


class Pipeline:
    """Full compilation pipeline for a MECSL source file."""

    def __init__(self, entry_path: str) -> None:
        self._entry = Path(entry_path).resolve()
        self._bag = DiagnosticBag()
        # Per-module caches
        self._programs: dict[str, ProgramNode] = {}      # path -> ProgramNode
        self._expanded: dict[str, ProgramNode] = {}      # path -> expanded AST
        self._ir_modules: dict[str, list[Instruction]] = {}  # stem -> instructions
        self._visited: set[str] = set()
        self._in_stack: set[str] = set()

    # ------------------------------------------------------------------ public
    @property
    def bag(self) -> DiagnosticBag:
        return self._bag

    def lex(self) -> list:
        """Return tokens for the entry file only."""
        src = self._entry.read_text(encoding="utf-8")
        lexer = Lexer(src, str(self._entry), self._bag)
        return lexer.tokenize()

    def parse_entry(self) -> ProgramNode:
        """Parse (without import resolution) the entry file."""
        return self._parse_file(self._entry)

    def run(self) -> dict[str, Any]:
        """Full pipeline: returns the loaded configuration dict."""
        self._compile_recursive(self._entry)
        if self._bag.has_errors:
            self._bag.raise_if_errors()

        linker = Linker(self._bag)
        linked = linker.link(self._ir_modules, self._entry.stem)
        if self._bag.has_errors:
            self._bag.raise_if_errors()

        loader = Loader(self._bag)
        result = loader.load(linked)
        if self._bag.has_errors:
            self._bag.raise_if_errors()
        return result

    def get_linked_module(self) -> LinkedModule:
        self._compile_recursive(self._entry)
        if self._bag.has_errors:
            self._bag.raise_if_errors()
        linker = Linker(self._bag)
        return linker.link(self._ir_modules, self._entry.stem)

    def get_expanded(self) -> ProgramNode:
        self._compile_recursive(self._entry)
        return self._expanded.get(str(self._entry),
                                  ProgramNode(source_file=str(self._entry)))

    def get_merged_symbol_table(self) -> SymbolTable:
        self._compile_recursive(self._entry)
        return self._build_merged_table()

    def get_ir(self) -> list[Instruction]:
        linked = self.get_linked_module()
        return linked.instructions

    # ----------------------------------------------------------------- private
    def _compile_recursive(self, path: Path) -> None:
        key = str(path)
        if key in self._visited:
            return
        if key in self._in_stack:
            span = UNKNOWN_SPAN
            self._bag.error("E402", f"Import cycle detected: {path.name}", span)
            return

        self._in_stack.add(key)

        if not path.exists():
            self._bag.error(
                "E401",
                f"File not found: {path}",
                UNKNOWN_SPAN,
                suggestion=f"Check that '{path.name}' exists.",
            )
            self._in_stack.discard(key)
            return

        program = self._parse_file(path)
        self._programs[key] = program

        # Resolve imports first
        for stmt in program.statements:
            if isinstance(stmt, ImportNode):
                imported_path = (path.parent / stmt.path).resolve()
                self._compile_recursive(imported_path)

        # Macro expansion
        mp = MacroProcessor(self._bag)
        mp.collect_definitions(program)
        expanded = mp.expand_program(program)
        self._expanded[key] = expanded

        # Symbol table
        table = SymbolTable(path.stem, self._bag)
        table.build_from_program(expanded)

        # Semantic analysis
        merged = self._build_merged_table()
        analyzer = SemanticAnalyzer(merged, self._bag)
        analyzer.analyze(expanded)

        # IR generation
        gen = IRGenerator(path.stem, self._bag)
        instructions = gen.generate(expanded)
        self._ir_modules[path.stem] = instructions

        self._in_stack.discard(key)
        self._visited.add(key)

    def _parse_file(self, path: Path) -> ProgramNode:
        src = path.read_text(encoding="utf-8")
        lexer = Lexer(src, str(path), self._bag)
        tokens = lexer.tokenize()
        parser = Parser(tokens, str(path), self._bag)
        return parser.parse()

    def _build_merged_table(self) -> SymbolTable:
        merged = SymbolTable("__merged__", self._bag)
        for key, prog in self._expanded.items():
            path = Path(key)
            mod_table = SymbolTable(path.stem, DiagnosticBag())
            mod_table.build_from_program(prog)
            merged.merge(mod_table)
        return merged
