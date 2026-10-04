"""Bytecode container and opcode definitions."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class Op(IntEnum):
    CONSTANT = 0
    NIL = 1
    TRUE = 2
    FALSE = 3
    POP = 4
    GET_GLOBAL = 5
    DEFINE_GLOBAL = 6
    SET_GLOBAL = 7
    GET_LOCAL = 8
    SET_LOCAL = 9
    GET_LOCAL_CELL = 10
    SET_LOCAL_CELL = 11
    GET_UPVALUE = 12
    SET_UPVALUE = 13
    MAKE_CELL = 14
    CAPTURE_LOCAL = 15
    CAPTURE_UPVALUE = 16
    CAPTURE = 17
    JUMP = 18
    JUMP_IF_FALSE = 19
    LOOP = 20
    CALL = 21
    RETURN = 22
    CLOSURE = 23
    CLASS = 24
    METHOD = 25
    INHERIT = 26
    GET_PROPERTY = 27
    SET_PROPERTY = 28
    GET_INDEX = 29
    SET_INDEX = 30
    BUILD_LIST = 31
    BUILD_MAP = 32
    NEGATE = 33
    NOT = 34
    ADD = 35
    SUBTRACT = 36
    MULTIPLY = 37
    DIVIDE = 38
    MODULO = 39
    EQUAL = 40
    GREATER = 41
    LESS = 42
    NOT_EQUAL = 43
    LESS_EQUAL = 44
    GREATER_EQUAL = 45


OPERAND_COUNT = {
    Op.CONSTANT: 1,
    Op.GET_GLOBAL: 1,
    Op.DEFINE_GLOBAL: 1,
    Op.SET_GLOBAL: 1,
    Op.GET_LOCAL: 1,
    Op.SET_LOCAL: 1,
    Op.GET_LOCAL_CELL: 1,
    Op.SET_LOCAL_CELL: 1,
    Op.GET_UPVALUE: 1,
    Op.SET_UPVALUE: 1,
    Op.CAPTURE_LOCAL: 1,
    Op.CAPTURE_UPVALUE: 1,
    Op.JUMP: 1,
    Op.JUMP_IF_FALSE: 1,
    Op.LOOP: 1,
    Op.CALL: 1,
    Op.CLOSURE: 1,
    Op.CLASS: 1,
    Op.METHOD: 1,
    Op.GET_PROPERTY: 1,
    Op.SET_PROPERTY: 1,
    Op.BUILD_LIST: 1,
    Op.BUILD_MAP: 1,
}


class Chunk:
    def __init__(self) -> None:
        self.code: list[int] = []
        self.constants: list[Any] = []
        self.lines: list[int] = []

    def write(self, opcode: Op, operand: int | None = None, line: int = 0) -> int:
        offset = len(self.code)
        self.code.append(int(opcode))
        self.lines.append(line)
        if operand is not None:
            self.code.append(operand)
            self.lines.append(line)
        return offset

    def add_constant(self, value: Any) -> int:
        self.constants.append(value)
        return len(self.constants) - 1

    def patch_jump(self, offset: int, target: int) -> None:
        self.code[offset + 1] = target

    def line_at(self, instruction: int) -> int:
        return self.lines[instruction] if instruction < len(self.lines) else self.lines[-1] if self.lines else 0
