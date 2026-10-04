"""Bytecode compiler for the Nimbus language."""

from __future__ import annotations

from . import ast
from .chunk import Chunk, Op
from .errors import CompileError
from .objects import Function
from .resolver import Global, Local, Upvalue
from .tokens import TokenType


class LoopContext:
    def __init__(self) -> None:
        self.breaks: list[int] = []
        self.continues: list[int] = []


class FunctionCompiler:
    def __init__(self, function: ast.FunctionExpr, name: str = "<lambda>") -> None:
        self.function = function
        self.name = name
        self.chunk = Chunk()
        self.loops: list[LoopContext] = []
        self.temp_slot = function.slot_count

    def compile(self) -> Function:
        for statement in self.function.body:
            self._compile_stmt(statement)
        self._emit(Op.NIL, self.function.line)
        self._emit(Op.RETURN, self.function.line)
        return Function(
            chunk=self.chunk,
            name=self.name,
            arity=len(self.function.params),
            slot_count=max(self.function.slot_count, self.temp_slot),
            param_slots=list(self.function.param_slots),
            upvalues=[],
        )

    def _emit(self, opcode: Op, line: int = 0, operand: int | None = None) -> int:
        return self.chunk.write(opcode, operand, line)

    def _constant(self, value: object) -> int:
        return self.chunk.add_constant(value)

    def _emit_jump(self, opcode: Op, line: int) -> int:
        return self._emit(opcode, line, 0)

    def _patch_jump(self, offset: int) -> None:
        self.chunk.patch_jump(offset, len(self.chunk.code))

    def _emit_loop(self, target: int, line: int) -> None:
        self._emit(Op.LOOP, line, target)

    def _compile_stmt(self, statement: ast.Stmt) -> None:
        if isinstance(statement, ast.BlockStmt):
            for child in statement.statements:
                self._compile_stmt(child)
        elif isinstance(statement, ast.ExprStmt):
            self._compile_expr(statement.expression)
            self._emit(Op.POP, statement.line)
        elif isinstance(statement, ast.LetStmt):
            self._compile_let(statement)
        elif isinstance(statement, ast.FunctionDecl):
            self._compile_function_decl(statement)
        elif isinstance(statement, ast.ClassDecl):
            self._compile_class_decl(statement)
        elif isinstance(statement, ast.IfStmt):
            self._compile_if(statement)
        elif isinstance(statement, ast.WhileStmt):
            self._compile_while(statement)
        elif isinstance(statement, ast.ForStmt):
            self._compile_for(statement)
        elif isinstance(statement, ast.BreakStmt):
            if not self.loops:
                raise CompileError("'break' outside of a loop", statement.line, statement.column)
            loop = self.loops[-1]
            loop.breaks.append(self._emit_jump(Op.JUMP, statement.line))
        elif isinstance(statement, ast.ContinueStmt):
            if not self.loops:
                raise CompileError("'continue' outside of a loop", statement.line, statement.column)
            loop = self.loops[-1]
            loop.continues.append(self._emit_jump(Op.LOOP, statement.line))
        elif isinstance(statement, ast.ReturnStmt):
            if statement.value is not None:
                self._compile_expr(statement.value)
            else:
                self._emit(Op.NIL, statement.line)
            self._emit(Op.RETURN, statement.line)
        else:
            raise CompileError(f"unknown statement {type(statement).__name__}", statement.line, statement.column)

    def _compile_let(self, statement: ast.LetStmt) -> None:
        self._compile_expr(statement.initializer)
        self._bind_local_or_global(statement.name.lexeme, statement.variable, statement.line)

    def _bind_local_or_global(self, name: str, variable, line: int) -> None:
        if variable is None:
            self._emit(Op.DEFINE_GLOBAL, line, self._constant(name))
            return
        if variable.is_captured:
            self._emit(Op.MAKE_CELL, line)
            self._emit(Op.SET_LOCAL, line, variable.slot)
        else:
            self._emit(Op.SET_LOCAL, line, variable.slot)
        self._emit(Op.POP, line)

    def _compile_function_decl(self, statement: ast.FunctionDecl) -> None:
        self._compile_function_expr(statement.function, statement.name.lexeme)
        self._bind_local_or_global(statement.name.lexeme, statement.variable, statement.line)

    def _compile_class_decl(self, statement: ast.ClassDecl) -> None:
        has_superclass = 0
        if statement.superclass is not None:
            self._compile_expr(statement.superclass)
            has_superclass = 1
        self._emit(Op.CLASS, statement.line, self._constant(statement.name.lexeme))
        self.chunk.code.append(has_superclass)
        self.chunk.lines.append(statement.line)
        for method in statement.methods:
            self._compile_function_expr(method.function, method.name.lexeme)
            self._emit(Op.METHOD, method.line, self._constant(method.name.lexeme))
        self._bind_local_or_global(statement.name.lexeme, statement.variable, statement.line)

    def _compile_if(self, statement: ast.IfStmt) -> None:
        self._compile_expr(statement.condition)
        false_jump = self._emit_jump(Op.JUMP_IF_FALSE, statement.line)
        self._emit(Op.POP, statement.line)
        self._compile_stmt(statement.then_branch)
        end_jump = self._emit_jump(Op.JUMP, statement.line)
        self._patch_jump(false_jump)
        self._emit(Op.POP, statement.line)
        if statement.else_branch is not None:
            self._compile_stmt(statement.else_branch)
        self._patch_jump(end_jump)

    def _compile_while(self, statement: ast.WhileStmt) -> None:
        start = len(self.chunk.code)
        self._compile_expr(statement.condition)
        exit_jump = self._emit_jump(Op.JUMP_IF_FALSE, statement.line)
        self._emit(Op.POP, statement.line)
        loop = LoopContext()
        self.loops.append(loop)
        self._compile_stmt(statement.body)
        self.loops.pop()
        self._emit_loop(start, statement.line)
        self._patch_jump(exit_jump)
        self._emit(Op.POP, statement.line)
        for jump in loop.breaks:
            self._patch_jump(jump)
        for jump in loop.continues:
            self.chunk.patch_jump(jump, start)

    def _compile_for(self, statement: ast.ForStmt) -> None:
        if statement.variable is None:
            self._emit(Op.NIL, statement.line)
            self._emit(Op.DEFINE_GLOBAL, statement.line, self._constant(statement.variable_name))
        elif statement.variable.is_captured:
            self._emit(Op.NIL, statement.line)
            self._emit(Op.MAKE_CELL, statement.line)
            self._emit(Op.SET_LOCAL, statement.line, statement.variable.slot)
            self._emit(Op.POP, statement.line)
        iter_slot = self._alloc_temp()
        index_slot = self._alloc_temp()
        self._compile_expr(statement.iterable)
        self._emit(Op.SET_LOCAL, statement.line, iter_slot)
        self._emit(Op.CONSTANT, statement.line, self._constant(0))
        self._emit(Op.SET_LOCAL, statement.line, index_slot)

        condition_start = len(self.chunk.code)
        self._emit(Op.GET_LOCAL, statement.line, index_slot)
        self._emit(Op.GET_GLOBAL, statement.line, self._constant("len"))
        self._emit(Op.GET_LOCAL, statement.line, iter_slot)
        self._emit(Op.CALL, statement.line, 1)
        self._emit(Op.LESS, statement.line)
        exit_jump = self._emit_jump(Op.JUMP_IF_FALSE, statement.line)
        self._emit(Op.POP, statement.line)

        self._emit(Op.GET_LOCAL, statement.line, iter_slot)
        self._emit(Op.GET_LOCAL, statement.line, index_slot)
        self._emit(Op.GET_INDEX, statement.line)
        if statement.variable is None:
            self._emit(Op.SET_GLOBAL, statement.line, self._constant(statement.variable_name))
        elif statement.variable.is_captured:
            self._emit(Op.MAKE_CELL, statement.line)
            self._emit(Op.SET_LOCAL, statement.line, statement.variable.slot)
        else:
            self._emit(Op.SET_LOCAL, statement.line, statement.variable.slot)
        self._emit(Op.POP, statement.line)

        loop = LoopContext()
        self.loops.append(loop)
        self._compile_stmt(statement.body)
        self.loops.pop()

        increment_start = len(self.chunk.code)
        self._emit(Op.GET_LOCAL, statement.line, index_slot)
        self._emit(Op.CONSTANT, statement.line, self._constant(1))
        self._emit(Op.ADD, statement.line)
        self._emit(Op.SET_LOCAL, statement.line, index_slot)
        self._emit_loop(condition_start, statement.line)

        self._patch_jump(exit_jump)
        self._emit(Op.POP, statement.line)
        for jump in loop.breaks:
            self._patch_jump(jump)
        for jump in loop.continues:
            self.chunk.patch_jump(jump, increment_start)

    def _alloc_temp(self) -> int:
        slot = self.temp_slot
        self.temp_slot += 1
        return slot

    def _compile_function_expr(self, function: ast.FunctionExpr, name: str = "<lambda>") -> None:
        sub = FunctionCompiler(function, name)
        prototype = sub.compile()
        constant_index = self._constant(prototype)
        self._emit(Op.CLOSURE, function.line, constant_index)
        for descriptor in function.upvalues:
            if descriptor.is_local:
                self._emit(Op.CAPTURE_LOCAL, function.line, descriptor.index)
            else:
                self._emit(Op.CAPTURE_UPVALUE, function.line, descriptor.index)
            self._emit(Op.CAPTURE, function.line)

    def _compile_expr(self, expression: ast.Expr) -> None:
        if isinstance(expression, ast.Literal):
            self._compile_literal(expression)
        elif isinstance(expression, ast.Name):
            self._emit_get_resolution(expression.resolution, expression.line)
        elif isinstance(expression, ast.This):
            self._emit_get_resolution(expression.resolution, expression.line)
        elif isinstance(expression, ast.ListLiteral):
            for item in expression.items:
                self._compile_expr(item)
            self._emit(Op.BUILD_LIST, expression.line, len(expression.items))
        elif isinstance(expression, ast.MapLiteral):
            for key, value in zip(expression.keys, expression.values):
                self._compile_expr(key)
                self._compile_expr(value)
            self._emit(Op.BUILD_MAP, expression.line, len(expression.keys))
        elif isinstance(expression, ast.Unary):
            self._compile_expr(expression.right)
            opcode = Op.NEGATE if expression.operator == TokenType.MINUS else Op.NOT
            self._emit(opcode, expression.line)
        elif isinstance(expression, ast.Binary):
            self._compile_expr(expression.left)
            self._compile_expr(expression.right)
            self._emit(self._binary_opcode(expression.operator), expression.line)
        elif isinstance(expression, ast.Logical):
            self._compile_logical(expression)
        elif isinstance(expression, ast.Call):
            self._compile_expr(expression.callee)
            for argument in expression.arguments:
                self._compile_expr(argument)
            self._emit(Op.CALL, expression.line, len(expression.arguments))
        elif isinstance(expression, ast.GetItem):
            self._compile_expr(expression.target)
            self._compile_expr(expression.index)
            self._emit(Op.GET_INDEX, expression.line)
        elif isinstance(expression, ast.GetAttr):
            self._compile_expr(expression.target)
            self._emit(Op.GET_PROPERTY, expression.line, self._constant(expression.name))
        elif isinstance(expression, ast.Assign):
            self._compile_assignment(expression)
        elif isinstance(expression, ast.FunctionExpr):
            self._compile_function_expr(expression)
        else:
            raise CompileError(f"unknown expression {type(expression).__name__}", expression.line, expression.column)

    def _compile_literal(self, expression: ast.Literal) -> None:
        if expression.value is None:
            self._emit(Op.NIL, expression.line)
        elif expression.value is True:
            self._emit(Op.TRUE, expression.line)
        elif expression.value is False:
            self._emit(Op.FALSE, expression.line)
        else:
            self._emit(Op.CONSTANT, expression.line, self._constant(expression.value))

    def _binary_opcode(self, operator: TokenType) -> Op:
        return {
            TokenType.PLUS: Op.ADD,
            TokenType.MINUS: Op.SUBTRACT,
            TokenType.STAR: Op.MULTIPLY,
            TokenType.SLASH: Op.DIVIDE,
            TokenType.PERCENT: Op.MODULO,
            TokenType.EQUAL_EQUAL: Op.EQUAL,
            TokenType.BANG_EQUAL: Op.NOT_EQUAL,
            TokenType.GREATER: Op.GREATER,
            TokenType.GREATER_EQUAL: Op.GREATER_EQUAL,
            TokenType.LESS: Op.LESS,
            TokenType.LESS_EQUAL: Op.LESS_EQUAL,
        }[operator]

    def _compile_logical(self, expression: ast.Logical) -> None:
        self._compile_expr(expression.left)
        if expression.operator == TokenType.OR:
            false_jump = self._emit_jump(Op.JUMP_IF_FALSE, expression.line)
            end_jump = self._emit_jump(Op.JUMP, expression.line)
            self._patch_jump(false_jump)
            self._emit(Op.POP, expression.line)
            self._compile_expr(expression.right)
            self._patch_jump(end_jump)
        else:
            false_jump = self._emit_jump(Op.JUMP_IF_FALSE, expression.line)
            self._emit(Op.POP, expression.line)
            self._compile_expr(expression.right)
            self._patch_jump(false_jump)

    def _compile_assignment(self, expression: ast.Assign) -> None:
        target = expression.target
        if isinstance(target, ast.Name):
            self._compile_expr(expression.value)
            self._emit_set_name(target)
        elif isinstance(target, ast.GetAttr):
            self._compile_expr(expression.value)
            self._compile_expr(target.target)
            self._emit(Op.SET_PROPERTY, expression.line, self._constant(target.name))
        elif isinstance(target, ast.GetItem):
            self._compile_expr(expression.value)
            self._compile_expr(target.target)
            self._compile_expr(target.index)
            self._emit(Op.SET_INDEX, expression.line)
        else:
            raise CompileError("invalid assignment target", expression.line, expression.column)

    def _emit_get_resolution(self, resolution, line: int) -> None:
        if isinstance(resolution, Global):
            self._emit(Op.GET_GLOBAL, line, self._constant(resolution.name))
        elif isinstance(resolution, Local):
            captured = resolution.variable.is_captured if resolution.variable is not None else resolution.is_captured
            self._emit(Op.GET_LOCAL_CELL if captured else Op.GET_LOCAL, line, resolution.slot)
        elif isinstance(resolution, Upvalue):
            self._emit(Op.GET_UPVALUE, line, resolution.index)
        else:
            raise CompileError("unresolved variable", line)

    def _emit_set_name(self, name: ast.Name) -> None:
        resolution = name.resolution
        if isinstance(resolution, Global):
            self._emit(Op.SET_GLOBAL, name.line, self._constant(resolution.name))
        elif isinstance(resolution, Local):
            captured = resolution.variable.is_captured if resolution.variable is not None else resolution.is_captured
            self._emit(Op.SET_LOCAL_CELL if captured else Op.SET_LOCAL, name.line, resolution.slot)
        elif isinstance(resolution, Upvalue):
            self._emit(Op.SET_UPVALUE, name.line, resolution.index)
