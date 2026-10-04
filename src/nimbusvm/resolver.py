"""Semantic analysis: scopes, captured locals, and upvalues."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast
from .errors import ResolveError
from .tokens import Token


@dataclass
class Variable:
    name: str
    slot: int
    defined: bool = False
    is_captured: bool = False


@dataclass
class Global:
    name: str


@dataclass
class Local:
    slot: int
    is_captured: bool
    variable: Variable | None = None


@dataclass
class Upvalue:
    index: int


@dataclass
class UpvalueDesc:
    name: str
    is_local: bool
    index: int


class FunctionInfo:
    def __init__(self, scope_base: int, enclosing: "FunctionInfo | None", is_method: bool) -> None:
        self.scope_base = scope_base
        self.enclosing = enclosing
        self.is_method = is_method
        self.next_slot = 0
        self.upvalues: list[UpvalueDesc] = []
        self.upvalue_names: dict[str, int] = {}
        self.param_variables: list[Variable] = []

    def resolve_upvalue(self, resolver: "Resolver", name: str) -> int:
        if name in self.upvalue_names:
            return self.upvalue_names[name]
        for i in range(len(resolver.scopes) - 1, -1, -1):
            if name in resolver.scopes[i]:
                variable = resolver.scopes[i][name]
                owner = self
                for function in reversed(resolver.functions):
                    if i >= function.scope_base:
                        owner = function
                        break
                if owner is self or self.enclosing is owner:
                    variable.is_captured = True
                    self.upvalue_names[name] = len(self.upvalues)
                    self.upvalues.append(UpvalueDesc(name, True, variable.slot))
                    return self.upvalue_names[name]
                if self.enclosing is None:
                    return -1
                parent_index = self.enclosing.resolve_upvalue(resolver, name)
                if parent_index == -1:
                    return -1
                self.upvalue_names[name] = len(self.upvalues)
                self.upvalues.append(UpvalueDesc(name, False, parent_index))
                return self.upvalue_names[name]
        return -1


class Resolver:
    def __init__(self) -> None:
        self.scopes: list[dict[str, Variable]] = []
        self.functions: list[FunctionInfo] = []

    def resolve(self, statements: list[ast.Stmt]) -> None:
        for statement in statements:
            self._resolve_stmt(statement)

    def _begin_scope(self) -> None:
        if self.functions:
            self.scopes.append({})

    def _end_scope(self) -> None:
        if self.functions:
            self.scopes.pop()

    def _declare(self, name: Token) -> Variable | None:
        if not self.functions:
            return None
        info = self.functions[-1]
        variable = Variable(name.lexeme, info.next_slot)
        info.next_slot += 1
        self.scopes[-1][name.lexeme] = variable
        return variable

    def _define(self, variable: Variable | None) -> None:
        if variable is not None:
            variable.defined = True

    def _resolve_stmt(self, statement: ast.Stmt) -> None:
        if isinstance(statement, ast.BlockStmt):
            self._begin_scope()
            for child in statement.statements:
                self._resolve_stmt(child)
            self._end_scope()
        elif isinstance(statement, ast.LetStmt):
            variable = self._declare(statement.name)
            statement.variable = variable
            self._resolve_expr(statement.initializer)
            self._define(variable)
        elif isinstance(statement, ast.IfStmt):
            self._resolve_expr(statement.condition)
            self._resolve_stmt(statement.then_branch)
            if statement.else_branch is not None:
                self._resolve_stmt(statement.else_branch)
        elif isinstance(statement, ast.WhileStmt):
            self._resolve_expr(statement.condition)
            self._resolve_stmt(statement.body)
        elif isinstance(statement, ast.ForStmt):
            self._begin_scope()
            variable = self._declare(Token(type=statement.variable_name, lexeme=statement.variable_name, literal=None, line=statement.line, column=statement.column))
            self._define(variable)
            statement.variable = variable
            self._resolve_expr(statement.iterable)
            self._resolve_stmt(statement.body)
            self._end_scope()
        elif isinstance(statement, ast.BreakStmt) or isinstance(statement, ast.ContinueStmt):
            pass
        elif isinstance(statement, ast.ReturnStmt):
            if statement.value is not None:
                self._resolve_expr(statement.value)
        elif isinstance(statement, ast.ExprStmt):
            self._resolve_expr(statement.expression)
        elif isinstance(statement, ast.FunctionDecl):
            variable = self._declare(statement.name)
            self._define(variable)
            statement.variable = variable
            self._resolve_function(statement.function, False)
        elif isinstance(statement, ast.ClassDecl):
            variable = self._declare(statement.name)
            self._define(variable)
            statement.variable = variable
            if statement.superclass is not None:
                self._resolve_expr(statement.superclass)
            for method in statement.methods:
                self._resolve_function(method.function, True)
        else:
            raise ResolveError(f"unknown statement {type(statement).__name__}", statement.line, statement.column)

    def _resolve_function(self, function: ast.FunctionExpr, is_method: bool) -> None:
        info = FunctionInfo(
            scope_base=len(self.scopes),
            enclosing=self.functions[-1] if self.functions else None,
            is_method=is_method,
        )
        self.functions.append(info)
        self._begin_scope()
        if is_method:
            this_var = self._declare(Token(type=None, lexeme="this", literal=None, line=function.line, column=function.column))
            self._define(this_var)
            info.param_variables.append(this_var)
        for name in function.params:
            token = Token(type=None, lexeme=name, literal=None, line=function.line, column=function.column)
            variable = self._declare(token)
            self._define(variable)
            info.param_variables.append(variable)
        for statement in function.body:
            self._resolve_stmt(statement)
        self._end_scope()
        self.functions.pop()

        function.is_method = is_method
        function.slot_count = info.next_slot
        function.upvalues = info.upvalues
        function.param_slots = [(var.slot, var.is_captured) for var in info.param_variables]

    def _resolve_expr(self, expression: ast.Expr) -> None:
        if isinstance(expression, ast.Literal):
            return
        if isinstance(expression, ast.Name):
            self._resolve_name(expression)
        elif isinstance(expression, ast.ListLiteral):
            for item in expression.items:
                self._resolve_expr(item)
        elif isinstance(expression, ast.MapLiteral):
            for key, value in zip(expression.keys, expression.values):
                self._resolve_expr(key)
                self._resolve_expr(value)
        elif isinstance(expression, ast.Unary):
            self._resolve_expr(expression.right)
        elif isinstance(expression, ast.Binary):
            self._resolve_expr(expression.left)
            self._resolve_expr(expression.right)
        elif isinstance(expression, ast.Logical):
            self._resolve_expr(expression.left)
            self._resolve_expr(expression.right)
        elif isinstance(expression, ast.Call):
            self._resolve_expr(expression.callee)
            for argument in expression.arguments:
                self._resolve_expr(argument)
        elif isinstance(expression, ast.GetItem):
            self._resolve_expr(expression.target)
            self._resolve_expr(expression.index)
        elif isinstance(expression, ast.SetItem):
            self._resolve_expr(expression.target)
            self._resolve_expr(expression.index)
            self._resolve_expr(expression.value)
        elif isinstance(expression, ast.GetAttr):
            self._resolve_expr(expression.target)
        elif isinstance(expression, ast.SetAttr):
            self._resolve_expr(expression.target)
            self._resolve_expr(expression.value)
        elif isinstance(expression, ast.Assign):
            self._resolve_expr(expression.value)
            self._resolve_expr(expression.target)
        elif isinstance(expression, ast.FunctionExpr):
            self._resolve_function(expression, False)
        elif isinstance(expression, ast.This):
            if not self.functions:
                raise ResolveError("'this' can only be used inside a method", expression.line, expression.column)
            synthetic = ast.Name("this", expression.line, expression.column)
            self._resolve_name(synthetic)
            if isinstance(synthetic.resolution, Global):
                raise ResolveError("'this' can only be used inside a method", expression.line, expression.column)
            expression.resolution = synthetic.resolution
        else:
            raise ResolveError(f"unknown expression {type(expression).__name__}", expression.line, expression.column)

    def _resolve_name(self, name: ast.Name) -> None:
        for i in range(len(self.scopes) - 1, -1, -1):
            if name.name in self.scopes[i]:
                variable = self.scopes[i][name.name]
                if not variable.defined:
                    raise ResolveError("can't read a local variable in its own initializer", name.line, name.column)
                if self.functions and i < self.functions[-1].scope_base:
                    info = self.functions[-1]
                    enclosing = info.enclosing
                    if enclosing is not None and i >= enclosing.scope_base:
                        variable.is_captured = True
                        if name.name not in info.upvalue_names:
                            info.upvalue_names[name.name] = len(info.upvalues)
                            info.upvalues.append(UpvalueDesc(name.name, True, variable.slot))
                    else:
                        parent_index = enclosing.resolve_upvalue(self, name.name) if enclosing else -1
                        if parent_index == -1:
                            name.resolution = Global(name.name)
                            return
                        if name.name not in info.upvalue_names:
                            info.upvalue_names[name.name] = len(info.upvalues)
                            info.upvalues.append(UpvalueDesc(name.name, False, parent_index))
                    name.resolution = Upvalue(info.upvalue_names[name.name])
                else:
                    name.resolution = Local(variable.slot, variable.is_captured, variable)
                return
        name.resolution = Global(name.name)
