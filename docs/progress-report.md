# MECSL Progress Report

## Team
- Manan Oswal — Roll No. 51
- Siddhant Kumbhar — Roll No. 8
- Pranav Landge — Roll No. 12

---

## Completed

- [x] Repository structure
- [x] `pyproject.toml` with `src` layout and editable install
- [x] `source.py` — `SourceSpan` with merge and point helpers
- [x] `diagnostics.py` — `DiagnosticBag`, `Diagnostic`, `DiagnosticError`
- [x] `lexer/token.py` — `TokenKind` enum + `Token` dataclass
- [x] `lexer/lexer.py` — full lexer: whitespace, comments, strings, integers, keywords, error recovery
- [x] `parser/ast.py` — all required AST node dataclasses with source spans
- [x] `parser/parser.py` — recursive-descent parser for all language constructs
- [x] `macro/processor.py` — `MacroProcessor` with AST-based expansion, recursion guard, arg-count check
- [x] `symbols/tables.py` — `SymbolTable` with kind, type, module, visibility; merge for linking
- [x] `semantic/analyzer.py` — undefined ref, duplicate def, env args, run string, script uniqueness
- [x] `ir/instruction.py` — `Opcode` enum, `Instruction`, `LinkedModule` dataclasses
- [x] `ir/generator.py` — `IRGenerator` emitting all opcodes
- [x] `linker/linker.py` — topological sort, export table, unresolved symbol detection
- [x] `loader/loader.py` — env evaluation, reference resolution, hierarchical dict, JSON output
- [x] `pipeline.py` — full orchestration with recursive import resolution
- [x] `cli.py` + `__main__.py` — all 7 CLI commands with `--help` and exit codes
- [x] `examples/` — common.mecs, app.mecs, invalid_undefined_reference.mecs, invalid_macro_arguments.mecs, imported_app.mecs
- [x] `tests/` — 84 tests covering every module
- [x] `docs/` — language-specification.md, architecture.md, progress-report.md
- [x] `README.md` with install steps, CLI usage, examples, known limitations

---

## In Progress

- Import resolution works but `imported_app.mecs` (double-import) has not been tested for duplicate-symbol merging edge cases.

---

## Not Yet Implemented

- Nested objects (objects inside section values)
- Default macro parameters
- Conditional assignments (`if`/`else`)
- Multiple output formats (TOML, YAML, etc.)
- Graphical interface
- Incremental builds
- Safe command allow-list for `run`
- Object-module serialisation (`.mobj` files)
- Interactive REPL

---

## Test Results

```
84 passed in 0.82s
```

All 84 tests pass. Breakdown:
- `test_lexer.py` — 13 tests
- `test_parser.py` — 12 tests
- `test_macros.py` — 11 tests
- `test_symbols.py` — 9 tests
- `test_semantic.py` — 7 tests
- `test_ir.py` — 8 tests
- `test_linker.py` — 4 tests
- `test_loader.py` — 10 tests
- `test_integration.py` — 10 tests

---

## Demonstration Commands

```bash
python -m mecsl check examples/app.mecs
# → OK — no errors found.

python -m mecsl tokens examples/app.mecs
# → token stream with kinds, lexemes, and source locations

python -m mecsl expand examples/app.mecs
# → macro-expanded AST dump (SET_SERVER call replaced with two assignments)

python -m mecsl symbols examples/app.mecs
# → full symbol table across app + common modules

python -m mecsl ir examples/app.mecs
# → IR instructions (MODULE_BEGIN, SECTION_BEGIN, SET_VALUE, etc.)

python -m mecsl build examples/app.mecs --output build/app.json
# → linked + loaded JSON written to build/app.json

python -m mecsl run examples/app.mecs --dry-run
# → script plan: PRINT and [DRY-RUN] lines

python -m mecsl check examples/invalid_macro_arguments.mecs
# → [E302] Macro 'SET_PORT' expects 1 argument(s) but got 2.

python -m mecsl check examples/invalid_undefined_reference.mecs
# → [E203] Undefined reference 'database.missingHost'.
```

---

## Known Limitations

1. Macro parameters used as the first part of a qualified reference (`param.sub`) are not substituted.
2. The linker operates in-memory only; no `.mobj` serialisation.
3. `run` commands are always dry-run; no runtime command allow-list.
4. Sections cannot be defined more than once (no merge semantics for duplicate sections from separate files).

---

## Next Steps

1. Add merge semantics for duplicate section names from different imported modules.
2. Implement default macro parameters.
3. Add a safe command allow-list for `run`.
4. Improve qualified-reference substitution inside macro bodies.
5. Add serialisation of linked IR to `build/*.mobj` files.
