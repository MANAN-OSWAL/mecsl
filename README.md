# MECSL — Macro-Enabled Configuration and Scripting Language

A working prototype compiler/interpreter pipeline for a domain-specific language
designed to demonstrate core System Programming concepts: lexical analysis, parsing,
macro expansion, symbol tables, semantic validation, IR generation, linking, and loading.

---

## Team

| Name              | Roll No. |
|-------------------|----------|
| Manan Oswal       | 51       |
| Siddhant Kumbhar  | 8        |
| Pranav Landge     | 12       |

---

## Features

- **Lexical analysis** — tokeniser with full source-span tracking
- **Syntax analysis** — recursive-descent parser producing a typed AST
- **Macro processing** — parameterised macros expanded via AST deep-copy (no string replacement)
- **Symbol-table management** — per-module tables merged at link time
- **Semantic validation** — undefined references, duplicate definitions, env/run argument checks
- **Intermediate representation** — explicit opcode-based IR
- **Linking** — static linker resolves import graph and merges modules
- **Loading** — converts linked IR into a final JSON configuration
- **Error reporting** — structured diagnostics with codes, file, line, column, and suggestions

---

## Installation

```bash
python -m pip install -e .
```

Requires Python 3.11+. No third-party runtime dependencies.

---

## CLI Usage

```bash
# Tokenise a source file
python -m mecsl tokens examples/app.mecs

# Check for errors
python -m mecsl check examples/app.mecs

# Print macro-expanded AST
python -m mecsl expand examples/app.mecs

# Print symbol table
python -m mecsl symbols examples/app.mecs

# Print IR instructions
python -m mecsl ir examples/app.mecs

# Build final JSON
python -m mecsl build examples/app.mecs --output build/app.json

# Run script blocks (always dry-run — no shell execution)
python -m mecsl run examples/app.mecs --dry-run
```

---

## Example Input (examples/app.mecs)

```
import "common.mecs";

macro SET_SERVER(hostValue, portValue) {
    server.host = hostValue;
    server.port = portValue;
}

[application] {
    name = "College Portal";
    environment = env("APP_ENV", "development");
    maxUsers = 500;
    defaultHost = server_defaults.host;
}

SET_SERVER("localhost", 8080);

script start {
    print "Starting College Portal";
    run "college-portal";
}
```

## Example Output (build/app.json)

```json
{
  "application": {
    "defaultHost": "localhost",
    "environment": "development",
    "maxUsers": 500,
    "name": "College Portal"
  },
  "logging": {
    "enabled": true,
    "level": "info"
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

---

## Error Demonstration

```bash
# Macro argument mismatch → E302
python -m mecsl check examples/invalid_macro_arguments.mecs

# Undefined reference → E203
python -m mecsl check examples/invalid_undefined_reference.mecs
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

84 tests pass covering every module.

---

## Known Limitations

- Nested objects (objects inside objects beyond one level) are not yet supported.
- Macro parameters used as qualified references (`param.subkey`) are not fully substituted.
- The linker operates entirely in-memory; no object file serialisation.
- `run` commands are always dry-run; no command allow-list yet.
- No REPL or graphical interface.
