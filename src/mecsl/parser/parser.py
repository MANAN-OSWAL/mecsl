"""Recursive-descent parser for MECSL.

Design decision: the parser only builds the AST; it does NOT execute macros,
resolve imports, or perform semantic checks. Those are handled by later phases.
"""

from __future__ import annotations

from typing import Optional

from mecsl.diagnostics import DiagnosticBag
from mecsl.source import SourceSpan
from mecsl.lexer.token import Token, TokenKind
from mecsl.parser.ast import (
    ProgramNode, ImportNode, MacroDefinitionNode, MacroCallNode,
    SectionNode, AssignmentNode, ScriptNode, PrintNode, RunNode,
    IdentifierNode, LiteralNode, ListNode, ReferenceNode, FunctionCallNode,
    StatementNode, ValueNode,
)


class Parser:
    """Converts a token list into a ProgramNode AST."""

    def __init__(
        self,
        tokens: list[Token],
        filename: str,
        bag: DiagnosticBag,
    ) -> None:
        self._tokens = tokens
        self._filename = filename
        self._bag = bag
        self._pos = 0

    # ------------------------------------------------------------------ public
    def parse(self) -> ProgramNode:
        stmts: list[StatementNode] = []
        while not self._at_eof():
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        span = SourceSpan(self._filename, 1, 1,
                          self._current().source_span.end_line,
                          self._current().source_span.end_column)
        return ProgramNode(source_span=span, statements=stmts,
                           source_file=self._filename)

    # ----------------------------------------------------------------- internal
    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]  # EOF

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _at_eof(self) -> bool:
        return self._current().kind == TokenKind.EOF

    def _check(self, *kinds: TokenKind) -> bool:
        return self._current().kind in kinds

    def _match(self, *kinds: TokenKind) -> Optional[Token]:
        if self._current().kind in kinds:
            return self._advance()
        return None

    def _expect(self, kind: TokenKind, suggestion: str = "") -> Token:
        tok = self._match(kind)
        if tok is None:
            cur = self._current()
            msg = (f"Expected {kind.name} but got "
                   f"{cur.kind.name} ({cur.lexeme!r})")
            self._bag.error("E201", msg, cur.source_span,
                            suggestion=suggestion or f"Add {kind.name}.")
            # Return a synthetic token so parsing continues
            return Token(kind, "", None, cur.source_span)
        return tok

    def _expect_semicolon(self) -> None:
        self._expect(TokenKind.SEMICOLON,
                     suggestion="Add ';' at the end of the statement.")

    # --------------------------------------------------------- statement dispatch
    def _parse_statement(self) -> Optional[StatementNode]:
        cur = self._current()

        if cur.kind == TokenKind.IMPORT:
            return self._parse_import()
        if cur.kind == TokenKind.MACRO:
            return self._parse_macro_definition()
        if cur.kind == TokenKind.SCRIPT:
            return self._parse_script()
        if cur.kind == TokenKind.LBRACKET:
            return self._parse_section()
        if cur.kind == TokenKind.IDENTIFIER:
            # Could be: macro call  OR  qualified assignment
            return self._parse_identifier_led_statement()

        # Unexpected token — skip it and report
        self._bag.error(
            "E201",
            f"Unexpected token {cur.kind.name} ({cur.lexeme!r}) at top level.",
            cur.source_span,
        )
        self._advance()
        return None

    # ------------------------------------------------------------------ import
    def _parse_import(self) -> ImportNode:
        start = self._advance()  # consume 'import'
        path_tok = self._expect(TokenKind.STRING,
                                suggestion='Provide a quoted path, e.g. import "file.mecs";')
        self._expect_semicolon()
        span = start.source_span.merge(path_tok.source_span)
        return ImportNode(source_span=span, path=path_tok.value or "")

    # --------------------------------------------------------- macro definition
    def _parse_macro_definition(self) -> MacroDefinitionNode:
        start = self._advance()  # consume 'macro'
        name_tok = self._expect(TokenKind.IDENTIFIER,
                                suggestion="Provide a macro name.")
        self._expect(TokenKind.LPAREN, suggestion="Add '(' after macro name.")
        params = self._parse_param_list()
        self._expect(TokenKind.RPAREN, suggestion="Close parameter list with ')'.")
        self._expect(TokenKind.LBRACE, suggestion="Open macro body with '{'.")
        body = self._parse_body_statements()
        end = self._expect(TokenKind.RBRACE, suggestion="Close macro body with '}'.")
        span = start.source_span.merge(end.source_span)
        return MacroDefinitionNode(source_span=span,
                                   name=name_tok.lexeme,
                                   parameters=params,
                                   body=body)

    def _parse_param_list(self) -> list[str]:
        params: list[str] = []
        if self._check(TokenKind.RPAREN):
            return params
        tok = self._expect(TokenKind.IDENTIFIER)
        params.append(tok.lexeme)
        while self._match(TokenKind.COMMA):
            tok = self._expect(TokenKind.IDENTIFIER)
            params.append(tok.lexeme)
        return params

    def _parse_body_statements(self) -> list[StatementNode]:
        stmts: list[StatementNode] = []
        while not self._check(TokenKind.RBRACE) and not self._at_eof():
            stmt = self._parse_body_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _parse_body_statement(self) -> Optional[StatementNode]:
        cur = self._current()
        if cur.kind == TokenKind.PRINT:
            return self._parse_print()
        if cur.kind == TokenKind.RUN:
            return self._parse_run()
        if cur.kind == TokenKind.IDENTIFIER:
            return self._parse_identifier_led_statement()
        # Skip unknown
        self._bag.error("E201",
                        f"Unexpected token {cur.kind.name} in body.",
                        cur.source_span)
        self._advance()
        return None

    # ------------------------------------------------------------------ section
    def _parse_section(self) -> SectionNode:
        start = self._advance()  # consume '['
        name_tok = self._expect(TokenKind.IDENTIFIER,
                                suggestion="Provide a section name.")
        self._expect(TokenKind.RBRACKET, suggestion="Close section name with ']'.")
        self._expect(TokenKind.LBRACE, suggestion="Open section body with '{'.")
        assignments: list[AssignmentNode] = []
        while not self._check(TokenKind.RBRACE) and not self._at_eof():
            stmt = self._parse_body_statement()
            if isinstance(stmt, AssignmentNode):
                assignments.append(stmt)
            elif stmt is not None:
                self._bag.error("E201",
                                "Only assignments are allowed inside sections.",
                                stmt.source_span)
        end = self._expect(TokenKind.RBRACE,
                           suggestion="Close section body with '}'.")
        span = start.source_span.merge(end.source_span)
        return SectionNode(source_span=span,
                           name=name_tok.lexeme,
                           body=assignments)

    # -------------------------------------------------------- identifier-led stmt
    def _parse_identifier_led_statement(self) -> Optional[StatementNode]:
        """Handles macro calls and qualified assignments."""
        name_tok = self._advance()  # IDENTIFIER

        # Check for macro call:  NAME(...)
        if self._check(TokenKind.LPAREN):
            return self._parse_macro_call(name_tok)

        # Qualified name or simple assignment target
        parts = [name_tok.lexeme]
        while self._check(TokenKind.DOT):
            self._advance()  # consume '.'
            part = self._expect(TokenKind.IDENTIFIER,
                                suggestion="Expected identifier after '.'.")
            parts.append(part.lexeme)

        self._expect(TokenKind.EQUALS, suggestion="Add '=' after the key name.")
        value = self._parse_value()
        self._expect_semicolon()
        span = name_tok.source_span.merge(self._tokens[self._pos - 1].source_span)
        return AssignmentNode(source_span=span, target=parts, value=value)

    def _parse_macro_call(self, name_tok: Token) -> MacroCallNode:
        self._advance()  # consume '('
        args = self._parse_arg_list()
        end = self._expect(TokenKind.RPAREN,
                           suggestion="Close argument list with ')'.")
        self._expect_semicolon()
        span = name_tok.source_span.merge(end.source_span)
        return MacroCallNode(source_span=span,
                             name=name_tok.lexeme,
                             arguments=args)

    def _parse_arg_list(self) -> list[ValueNode]:
        args: list[ValueNode] = []
        if self._check(TokenKind.RPAREN):
            return args
        args.append(self._parse_value())
        while self._match(TokenKind.COMMA):
            args.append(self._parse_value())
        return args

    # ------------------------------------------------------------------ script
    def _parse_script(self) -> ScriptNode:
        start = self._advance()  # consume 'script'
        name_tok = self._expect(TokenKind.IDENTIFIER,
                                suggestion="Provide a script block name.")
        self._expect(TokenKind.LBRACE, suggestion="Open script body with '{'.")
        body = []
        while not self._check(TokenKind.RBRACE) and not self._at_eof():
            cur = self._current()
            if cur.kind == TokenKind.PRINT:
                body.append(self._parse_print())
            elif cur.kind == TokenKind.RUN:
                body.append(self._parse_run())
            else:
                self._bag.error("E201",
                                f"Unexpected {cur.kind.name} in script body.",
                                cur.source_span)
                self._advance()
        end = self._expect(TokenKind.RBRACE,
                           suggestion="Close script body with '}'.")
        span = start.source_span.merge(end.source_span)
        return ScriptNode(source_span=span, name=name_tok.lexeme, body=body)

    # ------------------------------------------------------------------ print
    def _parse_print(self) -> PrintNode:
        start = self._advance()  # consume 'print'
        val = self._parse_value()
        self._expect_semicolon()
        span = start.source_span.merge(self._tokens[self._pos - 1].source_span)
        return PrintNode(source_span=span, value=val)

    # ------------------------------------------------------------------ run
    def _parse_run(self) -> RunNode:
        start = self._advance()  # consume 'run'
        val = self._parse_value()
        self._expect_semicolon()
        span = start.source_span.merge(self._tokens[self._pos - 1].source_span)
        return RunNode(source_span=span, command=val)

    # ------------------------------------------------------------------ value
    def _parse_value(self) -> ValueNode:
        cur = self._current()

        if cur.kind == TokenKind.STRING:
            self._advance()
            return LiteralNode(source_span=cur.source_span, value=cur.value)

        if cur.kind == TokenKind.INTEGER:
            self._advance()
            return LiteralNode(source_span=cur.source_span, value=cur.value)

        if cur.kind == TokenKind.TRUE:
            self._advance()
            return LiteralNode(source_span=cur.source_span, value=True)

        if cur.kind == TokenKind.FALSE:
            self._advance()
            return LiteralNode(source_span=cur.source_span, value=False)

        if cur.kind == TokenKind.LBRACKET:
            return self._parse_list()

        if cur.kind == TokenKind.ENV:
            return self._parse_env_call()

        if cur.kind == TokenKind.IDENTIFIER:
            return self._parse_reference_or_identifier()

        # Error fallback
        self._bag.error("E201",
                        f"Expected a value but got {cur.kind.name} ({cur.lexeme!r}).",
                        cur.source_span)
        return LiteralNode(source_span=cur.source_span, value=None)

    def _parse_list(self) -> ListNode:
        start = self._advance()  # consume '['
        elements: list[ValueNode] = []
        if not self._check(TokenKind.RBRACKET):
            elements.append(self._parse_value())
            while self._match(TokenKind.COMMA):
                if self._check(TokenKind.RBRACKET):
                    break
                elements.append(self._parse_value())
        end = self._expect(TokenKind.RBRACKET,
                           suggestion="Close list with ']'.")
        span = start.source_span.merge(end.source_span)
        return ListNode(source_span=span, elements=elements)

    def _parse_env_call(self) -> FunctionCallNode:
        start = self._advance()  # consume 'env'
        self._expect(TokenKind.LPAREN, suggestion="Add '(' after 'env'.")
        args = self._parse_arg_list()
        end = self._expect(TokenKind.RPAREN, suggestion="Close 'env(...)' with ')'.")
        span = start.source_span.merge(end.source_span)
        return FunctionCallNode(source_span=span, name="env", args=args)

    def _parse_reference_or_identifier(self) -> ValueNode:
        """Parse  name  or  name.name.name  — could be a ref or bare ident."""
        first = self._advance()  # IDENTIFIER
        if not self._check(TokenKind.DOT):
            # Check if next token is LPAREN => macro call used as value (not supported)
            return IdentifierNode(source_span=first.source_span, name=first.lexeme)
        # Qualified reference
        parts = [first.lexeme]
        while self._check(TokenKind.DOT):
            self._advance()  # consume '.'
            part = self._expect(TokenKind.IDENTIFIER)
            parts.append(part.lexeme)
        span = first.source_span.merge(self._tokens[self._pos - 1].source_span)
        return ReferenceNode(source_span=span, parts=parts)
