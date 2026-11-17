# MECSL Language Specification — Version 1

## Tokens

| Token       | Pattern                         |
|-------------|----------------------------------|
| INTEGER     | `[0-9]+`                        |
| STRING      | `"..."` with `\n \t \r \" \\`   |
| TRUE        | `true`                          |
| FALSE       | `false`                         |
| IMPORT      | `import`                        |
| MACRO       | `macro`                         |
| SCRIPT      | `script`                        |
| PRINT       | `print`                         |
| RUN         | `run`                           |
| ENV         | `env`                           |
| IDENTIFIER  | `[a-zA-Z_][a-zA-Z0-9_]*`       |
| LBRACE      | `{`                             |
| RBRACE      | `}`                             |
| LBRACKET    | `[`                             |
| RBRACKET    | `]`                             |
| LPAREN      | `(`                             |
| RPAREN      | `)`                             |
| COMMA       | `,`                             |
| DOT         | `.`                             |
| EQUALS      | `=`                             |
| SEMICOLON   | `;`                             |
| EOF         | end of input                    |

Comments begin with `#` and extend to the end of the line.

---

## Grammar (EBNF)

```
program       = statement* EOF
statement     = import | macro_def | section | assignment | macro_call | script
import        = "import" STRING ";"
macro_def     = "macro" IDENTIFIER "(" param_list ")" "{" statement* "}"
param_list    = (IDENTIFIER ("," IDENTIFIER)*)?
section       = "[" IDENTIFIER "]" "{" assignment* "}"
assignment    = qualified_name "=" value ";"
qualified_name= IDENTIFIER ("." IDENTIFIER)*
macro_call    = IDENTIFIER "(" arg_list ")" ";"
arg_list      = (value ("," value)*)?
script        = "script" IDENTIFIER "{" script_cmd* "}"
script_cmd    = print_cmd | run_cmd
print_cmd     = "print" value ";"
run_cmd       = "run" value ";"
value         = STRING | INTEGER | "true" | "false" | list | env_call
              | qualified_name
list          = "[" (value ("," value)*)? "]"
env_call      = "env" "(" STRING ("," value)? ")"
```

---

## Values

| Kind      | Example               | Python type |
|-----------|-----------------------|-------------|
| String    | `"hello"`             | `str`       |
| Integer   | `8080`                | `int`       |
| Boolean   | `true` / `false`      | `bool`      |
| List      | `["a", "b"]`          | `list`      |
| Reference | `server.host`         | resolved    |
| Env       | `env("PORT", 8080)`   | `str`/any   |

---

## Statements

**Import** — loads another `.mecs` file. Path is relative to the importing file.
```
import "common.mecs";
```

**Section** — groups key-value assignments under a named scope.
```
[server] {
    host = "localhost";
    port = 8080;
}
```

**Assignment** — assigns a value to a qualified key.
```
server.host = "remotehost";
```

**Macro definition** — parameterised block of statements.
```
macro SET_SERVER(h, p) {
    server.host = h;
    server.port = p;
}
```

**Macro call** — expands the macro inline at that position.
```
SET_SERVER("localhost", 8080);
```

**Script block** — named sequence of safe commands.
```
script start {
    print "Starting";
    run "myapp";
}
```

---

## Macro Rules

- Macros must be defined before they are called (within the same file).
- The argument count must exactly match the parameter count.
- Recursive macro expansion is limited to depth 32.
- Macro definitions are removed from the executable statement stream after expansion.
- Expansion is AST-based (no string replacement).

---

## Import Rules

- Import paths are relative to the importing file.
- Missing files produce error `E401`.
- Import cycles produce error `E402`.
- Declaration collection happens before reference validation, so a referenced key
  may be defined in an imported file.

---

## Error Codes

| Code | Description                      |
|------|----------------------------------|
| E101 | Invalid character                |
| E102 | Unterminated string              |
| E201 | Unexpected token                 |
| E202 | Missing delimiter                |
| E203 | Undefined reference              |
| E204 | Duplicate definition             |
| E301 | Undefined macro                  |
| E302 | Macro argument mismatch          |
| E303 | Recursive macro expansion        |
| E401 | Import file not found            |
| E402 | Import cycle                     |
| E601 | Disallowed runtime command       |
