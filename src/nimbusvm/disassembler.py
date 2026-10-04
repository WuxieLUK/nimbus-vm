"""Human-readable bytecode disassembly."""

from __future__ import annotations

from .chunk import OPERAND_COUNT, Chunk, Op
from .objects import Function


def _constant_label(value: object) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, Function):
        return f"<fn {value.name}>"
    return str(value)


def disassemble_function(function: Function, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = "  " * indent
    lines.append(f"{prefix}== function {function.name} arity={function.arity} slots={function.slot_count} ==")
    lines.extend(_disassemble_chunk(function.chunk, prefix))
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            lines.append("")
            lines.extend(disassemble_function(constant, indent + 1))
    return lines


def _disassemble_chunk(chunk: Chunk, prefix: str) -> list[str]:
    lines: list[str] = []
    ip = 0
    while ip < len(chunk.code):
        start = ip
        opcode = Op(chunk.code[ip])
        ip += 1
        operand_count = OPERAND_COUNT.get(opcode, 0)
        operands = chunk.code[ip : ip + operand_count]
        ip += operand_count
        if opcode == Op.CLASS:
            has_superclass = chunk.code[ip]
            ip += 1
            operand_text = f"{chunk.constants[operands[0]]!r} super={has_superclass}"
        else:
            operand_text = _operand_text(opcode, operands, chunk)
        line = chunk.line_at(start)
        lines.append(f"{prefix}{start:04d}  {opcode.name:<18} {operand_text}   ; line {line}")
    return lines


def _operand_text(opcode: Op, operands: list[int], chunk: Chunk) -> str:
    if not operands:
        return ""
    if opcode in {
        Op.CONSTANT,
        Op.GET_GLOBAL,
        Op.DEFINE_GLOBAL,
        Op.SET_GLOBAL,
        Op.GET_PROPERTY,
        Op.SET_PROPERTY,
        Op.METHOD,
        Op.CLOSURE,
    }:
        return _constant_label(chunk.constants[operands[0]])
    return " ".join(str(value) for value in operands)


def disassemble(function: Function) -> str:
    return "\n".join(disassemble_function(function))
