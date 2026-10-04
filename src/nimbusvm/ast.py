"""Abstract syntax tree nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .tokens import Token, TokenType


class Node:
    line: int
    column: int


@dataclass
class Literal(Node):
    value: Any
    line: int = 0
    column: int = 0


@dataclass
class Name(Node):
    name: str
    line: int = 0
    column: int = 0


@dataclass
class ListLiteral(Node):
    items: list["Expr"] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class MapLiteral(Node):
    keys: list["Expr"] = field(default_factory=list)
    values: list["Expr"] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class Unary(Node):
    operator: TokenType
    right: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class Binary(Node):
    left: "Expr"
    operator: TokenType
    right: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class Logical(Node):
    left: "Expr"
    operator: TokenType
    right: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class Call(Node):
    callee: "Expr"
    arguments: list["Expr"] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class GetItem(Node):
    target: "Expr"
    index: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class SetItem(Node):
    target: "Expr"
    index: "Expr"
    value: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class GetAttr(Node):
    target: "Expr"
    name: str
    line: int = 0
    column: int = 0


@dataclass
class SetAttr(Node):
    target: "Expr"
    name: str
    value: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class Assign(Node):
    target: "Expr"
    value: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class FunctionExpr(Node):
    params: list[str] = field(default_factory=list)
    body: list["Stmt"] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class This(Node):
    line: int = 0
    column: int = 0


@dataclass
class ExprStmt(Node):
    expression: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class LetStmt(Node):
    name: Token
    initializer: "Expr"
    line: int = 0
    column: int = 0


@dataclass
class BlockStmt(Node):
    statements: list["Stmt"] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class IfStmt(Node):
    condition: "Expr"
    then_branch: "Stmt"
    else_branch: "Stmt | None" = None
    line: int = 0
    column: int = 0


@dataclass
class WhileStmt(Node):
    condition: "Expr"
    body: "Stmt"
    line: int = 0
    column: int = 0


@dataclass
class ForStmt(Node):
    variable_name: str
    iterable: "Expr"
    body: "Stmt"
    line: int = 0
    column: int = 0


@dataclass
class BreakStmt(Node):
    line: int = 0
    column: int = 0


@dataclass
class ContinueStmt(Node):
    line: int = 0
    column: int = 0


@dataclass
class ReturnStmt(Node):
    value: "Expr | None" = None
    line: int = 0
    column: int = 0


@dataclass
class FunctionDecl(Node):
    name: Token
    function: FunctionExpr
    line: int = 0
    column: int = 0


@dataclass
class ClassDecl(Node):
    name: Token
    superclass: Name | None
    methods: list[FunctionDecl] = field(default_factory=list)
    line: int = 0
    column: int = 0


Expr = (
    Literal
    | Name
    | ListLiteral
    | MapLiteral
    | Unary
    | Binary
    | Logical
    | Call
    | GetItem
    | SetItem
    | GetAttr
    | SetAttr
    | Assign
    | FunctionExpr
    | This
)

Stmt = (
    ExprStmt
    | LetStmt
    | BlockStmt
    | IfStmt
    | WhileStmt
    | ForStmt
    | BreakStmt
    | ContinueStmt
    | ReturnStmt
    | FunctionDecl
    | ClassDecl
)
