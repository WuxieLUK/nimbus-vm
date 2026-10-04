"""Recursive-descent parser with Pratt expression parsing."""

from __future__ import annotations

from . import ast
from .errors import ParseError
from .tokens import Token, TokenType


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0
        self.loop_depth = 0
        self.function_depth = 0

    def parse(self) -> list[ast.Stmt]:
        statements: list[ast.Stmt] = []
        while not self._check(TokenType.EOF):
            statements.append(self._declaration())
        return statements

    def _declaration(self) -> ast.Stmt:
        if self._match(TokenType.LET):
            return self._let_declaration()
        if self._match(TokenType.FN):
            return self._function_declaration()
        if self._match(TokenType.CLASS):
            return self._class_declaration()
        return self._statement()

    def _let_declaration(self) -> ast.LetStmt:
        name = self._consume(TokenType.IDENTIFIER, "expect a variable name after 'let'")
        initializer: ast.Expr = ast.Literal(None, name.line, name.column)
        if self._match(TokenType.EQUAL):
            initializer = self._expression()
        self._consume(TokenType.SEMICOLON, "expect ';' after variable declaration")
        return ast.LetStmt(name=name, initializer=initializer, line=name.line, column=name.column)

    def _function_declaration(self) -> ast.FunctionDecl:
        name = self._consume(TokenType.IDENTIFIER, "expect a function name")
        function = self._function_body(name)
        return ast.FunctionDecl(name=name, function=function, line=name.line, column=name.column)

    def _function_body(self, token: Token) -> ast.FunctionExpr:
        self._consume(TokenType.LEFT_PAREN, "expect '(' after function name")
        params: list[str] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                param = self._consume(TokenType.IDENTIFIER, "expect a parameter name")
                params.append(param.lexeme)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_PAREN, "expect ')' after parameters")
        self._consume(TokenType.LEFT_BRACE, "expect '{' before function body")
        self.function_depth += 1
        body = self._block_statements()
        self.function_depth -= 1
        return ast.FunctionExpr(params=params, body=body, line=token.line, column=token.column)

    def _class_declaration(self) -> ast.ClassDecl:
        name = self._consume(TokenType.IDENTIFIER, "expect a class name")
        superclass: ast.Name | None = None
        if self._match(TokenType.LESS):
            super_token = self._consume(TokenType.IDENTIFIER, "expect a superclass name")
            superclass = ast.Name(super_token.lexeme, super_token.line, super_token.column)
        self._consume(TokenType.LEFT_BRACE, "expect '{' before class body")
        methods: list[ast.FunctionDecl] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._check(TokenType.EOF):
            method_token = self._consume(TokenType.IDENTIFIER, "expect a method name")
            self._consume(TokenType.LEFT_PAREN, "expect '(' after method name")
            params: list[str] = []
            if not self._check(TokenType.RIGHT_PAREN):
                while True:
                    param = self._consume(TokenType.IDENTIFIER, "expect a parameter name")
                    params.append(param.lexeme)
                    if not self._match(TokenType.COMMA):
                        break
            self._consume(TokenType.RIGHT_PAREN, "expect ')' after parameters")
            self._consume(TokenType.LEFT_BRACE, "expect '{' before method body")
            self.function_depth += 1
            body = self._block_statements()
            self.function_depth -= 1
            function = ast.FunctionExpr(params=params, body=body, line=method_token.line, column=method_token.column)
            methods.append(ast.FunctionDecl(name=method_token, function=function, line=method_token.line, column=method_token.column))
        self._consume(TokenType.RIGHT_BRACE, "expect '}' after class body")
        return ast.ClassDecl(name=name, superclass=superclass, methods=methods, line=name.line, column=name.column)

    def _block_statements(self) -> list[ast.Stmt]:
        statements: list[ast.Stmt] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._check(TokenType.EOF):
            statements.append(self._declaration())
        self._consume(TokenType.RIGHT_BRACE, "expect '}' after block")
        return statements

    def _statement(self) -> ast.Stmt:
        if self._match(TokenType.LEFT_BRACE):
            return ast.BlockStmt(self._block_statements(), self._previous().line, self._previous().column)
        if self._match(TokenType.IF):
            return self._if_statement()
        if self._match(TokenType.WHILE):
            return self._while_statement()
        if self._match(TokenType.FOR):
            return self._for_statement()
        if self._match(TokenType.BREAK):
            self._consume(TokenType.SEMICOLON, "expect ';' after 'break'")
            if self.loop_depth == 0:
                raise ParseError("'break' outside of a loop", self._previous().line, self._previous().column)
            return ast.BreakStmt(self._previous().line, self._previous().column)
        if self._match(TokenType.CONTINUE):
            self._consume(TokenType.SEMICOLON, "expect ';' after 'continue'")
            if self.loop_depth == 0:
                raise ParseError("'continue' outside of a loop", self._previous().line, self._previous().column)
            return ast.ContinueStmt(self._previous().line, self._previous().column)
        if self._match(TokenType.RETURN):
            return self._return_statement()
        return self._expression_statement()

    def _if_statement(self) -> ast.IfStmt:
        token = self._previous()
        self._consume(TokenType.LEFT_PAREN, "expect '(' after 'if'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "expect ')' after condition")
        then_branch = self._statement()
        else_branch = self._statement() if self._match(TokenType.ELSE) else None
        return ast.IfStmt(condition, then_branch, else_branch, token.line, token.column)

    def _while_statement(self) -> ast.WhileStmt:
        token = self._previous()
        self._consume(TokenType.LEFT_PAREN, "expect '(' after 'while'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "expect ')' after condition")
        self.loop_depth += 1
        body = self._statement()
        self.loop_depth -= 1
        return ast.WhileStmt(condition, body, token.line, token.column)

    def _for_statement(self) -> ast.ForStmt:
        token = self._previous()
        self._consume(TokenType.LEFT_PAREN, "expect '(' after 'for'")
        if self._match(TokenType.LET):
            var_token = self._consume(TokenType.IDENTIFIER, "expect a loop variable after 'let'")
        else:
            var_token = self._consume(TokenType.IDENTIFIER, "expect a loop variable")
        self._consume(TokenType.IN, "expect 'in' in for loop")
        iterable = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "expect ')' after for clause")
        self.loop_depth += 1
        body = self._statement()
        self.loop_depth -= 1
        return ast.ForStmt(var_token.lexeme, iterable, body, token.line, token.column)

    def _return_statement(self) -> ast.ReturnStmt:
        token = self._previous()
        value: ast.Expr | None = None
        if not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._consume(TokenType.SEMICOLON, "expect ';' after return value")
        return ast.ReturnStmt(value, token.line, token.column)

    def _expression_statement(self) -> ast.ExprStmt:
        token = self._peek()
        expression = self._expression()
        self._consume(TokenType.SEMICOLON, "expect ';' after expression")
        return ast.ExprStmt(expression, token.line, token.column)

    def _expression(self) -> ast.Expr:
        return self._assignment()

    def _assignment(self) -> ast.Expr:
        left = self._or()
        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if isinstance(left, (ast.Name, ast.GetItem, ast.GetAttr)):
                return ast.Assign(left, value, equals.line, equals.column)
            raise ParseError("invalid assignment target", equals.line, equals.column)
        return left

    def _or(self) -> ast.Expr:
        left = self._and()
        while self._match(TokenType.OR):
            operator = self._previous()
            right = self._and()
            left = ast.Logical(left, operator.type, right, operator.line, operator.column)
        return left

    def _and(self) -> ast.Expr:
        left = self._equality()
        while self._match(TokenType.AND):
            operator = self._previous()
            right = self._equality()
            left = ast.Logical(left, operator.type, right, operator.line, operator.column)
        return left

    def _equality(self) -> ast.Expr:
        left = self._comparison()
        while self._match(TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            operator = self._previous()
            right = self._comparison()
            left = ast.Binary(left, operator.type, right, operator.line, operator.column)
        return left

    def _comparison(self) -> ast.Expr:
        left = self._term()
        while self._match(TokenType.GREATER, TokenType.GREATER_EQUAL, TokenType.LESS, TokenType.LESS_EQUAL):
            operator = self._previous()
            right = self._term()
            left = ast.Binary(left, operator.type, right, operator.line, operator.column)
        return left

    def _term(self) -> ast.Expr:
        left = self._factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            operator = self._previous()
            right = self._factor()
            left = ast.Binary(left, operator.type, right, operator.line, operator.column)
        return left

    def _factor(self) -> ast.Expr:
        left = self._unary()
        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            operator = self._previous()
            right = self._unary()
            left = ast.Binary(left, operator.type, right, operator.line, operator.column)
        return left

    def _unary(self) -> ast.Expr:
        if self._match(TokenType.BANG, TokenType.MINUS, TokenType.NOT):
            operator = self._previous()
            right = self._unary()
            return ast.Unary(operator.type, right, operator.line, operator.column)
        return self._call()

    def _call(self) -> ast.Expr:
        expression = self._primary()
        while True:
            if self._match(TokenType.LEFT_PAREN):
                expression = self._finish_call(expression)
            elif self._match(TokenType.LEFT_BRACKET):
                index = self._expression()
                token = self._consume(TokenType.RIGHT_BRACKET, "expect ']' after index")
                expression = ast.GetItem(expression, index, token.line, token.column)
            elif self._match(TokenType.DOT):
                name = self._consume(TokenType.IDENTIFIER, "expect a property name after '.'")
                expression = ast.GetAttr(expression, name.lexeme, name.line, name.column)
            else:
                break
        return expression

    def _finish_call(self, callee: ast.Expr) -> ast.Call:
        arguments: list[ast.Expr] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                arguments.append(self._expression())
                if not self._match(TokenType.COMMA):
                    break
        closing = self._consume(TokenType.RIGHT_PAREN, "expect ')' after arguments")
        return ast.Call(callee, arguments, closing.line, closing.column)

    def _primary(self) -> ast.Expr:
        if self._match(TokenType.FALSE):
            return ast.Literal(False, self._previous().line, self._previous().column)
        if self._match(TokenType.TRUE):
            return ast.Literal(True, self._previous().line, self._previous().column)
        if self._match(TokenType.NIL):
            return ast.Literal(None, self._previous().line, self._previous().column)
        if self._match(TokenType.NUMBER, TokenType.STRING):
            return ast.Literal(self._previous().literal, self._previous().line, self._previous().column)
        if self._match(TokenType.THIS):
            return ast.This(self._previous().line, self._previous().column)
        if self._match(TokenType.IDENTIFIER):
            return ast.Name(self._previous().lexeme, self._previous().line, self._previous().column)
        if self._match(TokenType.LEFT_PAREN):
            expression = self._expression()
            self._consume(TokenType.RIGHT_PAREN, "expect ')' after expression")
            return expression
        if self._match(TokenType.LEFT_BRACKET):
            return self._list_literal()
        if self._match(TokenType.MAP_OPEN):
            return self._map_literal()
        if self._match(TokenType.FN):
            return self._function_body(self._previous())
        raise ParseError("expect expression", self._peek().line, self._peek().column)

    def _list_literal(self) -> ast.ListLiteral:
        token = self._previous()
        items: list[ast.Expr] = []
        if not self._check(TokenType.RIGHT_BRACKET):
            while True:
                items.append(self._expression())
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_BRACKET, "expect ']' after list literal")
        return ast.ListLiteral(items, token.line, token.column)

    def _map_literal(self) -> ast.MapLiteral:
        token = self._previous()
        keys: list[ast.Expr] = []
        values: list[ast.Expr] = []
        if not self._check(TokenType.RIGHT_BRACE):
            while True:
                key = self._expression()
                self._consume(TokenType.COLON, "expect ':' between map key and value")
                value = self._expression()
                keys.append(key)
                values.append(value)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_BRACE, "expect '}' after map literal")
        return ast.MapLiteral(keys, values, token.line, token.column)

    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise ParseError(message, self._peek().line, self._peek().column)

    def _check(self, token_type: TokenType) -> bool:
        return self._peek().type == token_type

    def _advance(self) -> Token:
        if not self._check(TokenType.EOF):
            self.current += 1
        return self._previous()

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]
