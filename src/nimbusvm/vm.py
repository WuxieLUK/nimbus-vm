"""Stack-based bytecode virtual machine."""

from __future__ import annotations

import sys
from typing import Any

from . import ast
from .chunk import OPERAND_COUNT, Op
from .compiler import FunctionCompiler
from .errors import RuntimeNimbusError
from .objects import (
    BoundMethod,
    Builtin,
    Cell,
    Class,
    Function,
    Instance,
    NimbusList,
    NimbusMap,
    collect_garbage,
    heap_size,
    is_truthy,
    type_name,
)
from .resolver import Resolver
from .stdlib import ExitProgram, install_builtins


PENDING_CALL = object()


class CallFrame:
    def __init__(self, function: Function, slots: list[Any]) -> None:
        self.function = function
        self.slots = slots
        self.ip = 0
        self.is_constructor = False
        self.constructor_instance: Instance | None = None


class VM:
    def __init__(self, output=None, input_func=None) -> None:
        self.globals: dict[str, Any] = {}
        self.stack: list[Any] = []
        self.frames: list[CallFrame] = []
        self.output = output or sys.stdout
        self.input_func = input_func or input
        self.next_gc = 1024
        self.gc_enabled = True
        self.globals.update(install_builtins(self))

    def write(self, text: str) -> None:
        self.output.write(text)

    def read_input(self) -> str:
        return self.input_func()

    def stringify(self, value: Any) -> str:
        if value is None:
            return "nil"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return repr(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, NimbusList):
            return "[" + ", ".join(self.stringify(item) for item in value.items) + "]"
        if isinstance(value, NimbusMap):
            pairs = []
            for key, item in value.entries.items():
                pairs.append(f"{self.stringify(key)}: {self.stringify(item)}")
            return "#{" + ", ".join(pairs) + "}"
        return type_name(value)

    def interpret(self, statements: list[ast.Stmt]) -> Any:
        Resolver().resolve(statements)
        synthetic = ast.FunctionExpr(params=[], body=statements)
        synthetic.slot_count = 0
        synthetic.param_slots = []
        synthetic.upvalues = []
        synthetic.is_method = False
        main = FunctionCompiler(synthetic, "<script>").compile()
        self._call_function(main, [], 1)
        return self.run()

    def run(self) -> Any:
        try:
            while self.frames:
                self._maybe_gc()
                frame = self.frames[-1]
                chunk = frame.function.chunk
                if frame.ip >= len(chunk.code):
                    raise RuntimeNimbusError("execution fell off the end of a function")
                op_index = frame.ip
                opcode = Op(chunk.code[frame.ip])
                frame.ip += 1
                line = chunk.line_at(op_index)
                operand_count = OPERAND_COUNT.get(opcode, 0)
                operand = chunk.code[frame.ip] if operand_count else 0
                if operand_count:
                    frame.ip += operand_count
                self._execute(frame, opcode, operand, line)
        except ExitProgram as exc:
            raise exc
        except RuntimeNimbusError as exc:
            if exc.line is None:
                frame = self.frames[-1] if self.frames else None
                if frame is not None:
                    line = frame.function.chunk.line_at(max(0, frame.ip - 1))
                    exc = RuntimeNimbusError(exc.message, line)
            raise RuntimeNimbusError(self._with_stack_trace(exc.message), exc.line)
        return None

    def _with_stack_trace(self, message: str) -> str:
        trace = [message, "Stack trace:"]
        for frame in reversed(self.frames):
            line = frame.function.chunk.line_at(max(0, frame.ip - 1))
            trace.append(f"  in {frame.function.name} (line {line})")
        return "\n".join(trace)

    def _maybe_gc(self) -> None:
        if not self.gc_enabled:
            return
        if heap_size() < self.next_gc:
            return
        roots = list(self.globals.values())
        roots.extend(self.stack)
        for frame in self.frames:
            roots.append(frame.function)
            roots.extend(slot for slot in frame.slots if slot is not None)
        collect_garbage(roots)
        self.next_gc = heap_size() * 2 + 256

    def _execute(self, frame: CallFrame, opcode: Op, operand: int, line: int) -> None:
        stack = self.stack
        if opcode == Op.CONSTANT:
            stack.append(frame.function.chunk.constants[operand])
        elif opcode == Op.NIL:
            stack.append(None)
        elif opcode == Op.TRUE:
            stack.append(True)
        elif opcode == Op.FALSE:
            stack.append(False)
        elif opcode == Op.POP:
            stack.pop()
        elif opcode == Op.GET_GLOBAL:
            name = frame.function.chunk.constants[operand]
            if name not in self.globals:
                self._error(f"undefined variable '{name}'", line)
            stack.append(self.globals[name])
        elif opcode == Op.DEFINE_GLOBAL:
            name = frame.function.chunk.constants[operand]
            self.globals[name] = stack.pop()
        elif opcode == Op.SET_GLOBAL:
            name = frame.function.chunk.constants[operand]
            if name not in self.globals:
                self._error(f"undefined variable '{name}'", line)
            self.globals[name] = stack[-1]
        elif opcode == Op.GET_LOCAL:
            stack.append(frame.slots[operand])
        elif opcode == Op.SET_LOCAL:
            frame.slots[operand] = stack[-1]
        elif opcode == Op.GET_LOCAL_CELL:
            stack.append(frame.slots[operand].value)
        elif opcode == Op.SET_LOCAL_CELL:
            frame.slots[operand].value = stack[-1]
        elif opcode == Op.GET_UPVALUE:
            stack.append(frame.function.upvalues[operand].value)
        elif opcode == Op.SET_UPVALUE:
            frame.function.upvalues[operand].value = stack[-1]
        elif opcode == Op.MAKE_CELL:
            stack.append(Cell(stack.pop()))
        elif opcode == Op.CAPTURE_LOCAL:
            stack.append(frame.slots[operand])
        elif opcode == Op.CAPTURE_UPVALUE:
            stack.append(frame.function.upvalues[operand])
        elif opcode == Op.CAPTURE:
            cell = stack.pop()
            closure = stack[-1]
            closure.upvalues.append(cell)
        elif opcode == Op.JUMP:
            frame.ip = operand
        elif opcode == Op.JUMP_IF_FALSE:
            if not is_truthy(stack[-1]):
                frame.ip = operand
        elif opcode == Op.LOOP:
            frame.ip = operand
        elif opcode == Op.CALL:
            self._call(operand, line)
        elif opcode == Op.RETURN:
            self._return(frame)
        elif opcode == Op.CLOSURE:
            prototype = frame.function.chunk.constants[operand]
            stack.append(Function(prototype.chunk, prototype.name, prototype.arity, prototype.slot_count, prototype.param_slots, []))
        elif opcode == Op.CLASS:
            name = frame.function.chunk.constants[operand]
            superclass = None
            has_superclass = self._next_operand(frame)
            if has_superclass:
                superclass = stack.pop()
                if not isinstance(superclass, Class):
                    self._error("superclass must be a class", line)
            stack.append(Class(name, superclass))
        elif opcode == Op.METHOD:
            method = stack.pop()
            klass = stack[-1]
            klass.methods[frame.function.chunk.constants[operand]] = method
        elif opcode == Op.GET_PROPERTY:
            target = stack.pop()
            name = frame.function.chunk.constants[operand]
            stack.append(self._get_property(target, name, line))
        elif opcode == Op.SET_PROPERTY:
            target = stack.pop()
            name = frame.function.chunk.constants[operand]
            if not isinstance(target, Instance):
                self._error("only instances have fields", line)
            target.fields[name] = stack[-1]
        elif opcode == Op.GET_INDEX:
            index = stack.pop()
            container = stack.pop()
            stack.append(self._get_index(container, index, line))
        elif opcode == Op.SET_INDEX:
            index = stack.pop()
            container = stack.pop()
            self._set_index(container, index, stack[-1], line)
        elif opcode == Op.BUILD_LIST:
            items = [stack.pop() for _ in range(operand)]
            items.reverse()
            stack.append(NimbusList(items))
        elif opcode == Op.BUILD_MAP:
            entries = {}
            for _ in range(operand):
                value = stack.pop()
                key = stack.pop()
                entries[key] = value
            stack.append(NimbusMap(entries))
        elif opcode == Op.NEGATE:
            value = stack.pop()
            self._check_number(value, line, "unary minus")
            stack.append(-value)
        elif opcode == Op.NOT:
            stack.append(not is_truthy(stack.pop()))
        elif opcode in (Op.ADD, Op.SUBTRACT, Op.MULTIPLY, Op.DIVIDE, Op.MODULO, Op.EQUAL, Op.NOT_EQUAL, Op.GREATER, Op.GREATER_EQUAL, Op.LESS, Op.LESS_EQUAL):
            self._binary(opcode, line)
        else:
            self._error(f"unknown opcode {opcode}", line)

    def _next_operand(self, frame: CallFrame) -> int:
        value = frame.function.chunk.code[frame.ip]
        frame.ip += 1
        return value

    def _return(self, frame: CallFrame) -> None:
        self.frames.pop()
        if frame.is_constructor:
            if self.stack:
                self.stack.pop()
            result = frame.constructor_instance
        else:
            result = self.stack.pop() if self.stack else None
        self.stack.append(result)

    def _call(self, arg_count: int, line: int) -> None:
        if len(self.stack) < arg_count + 1:
            self._error("stack underflow on call", line)
        args = self.stack[-arg_count:] if arg_count else []
        callee = self.stack[-arg_count - 1]
        del self.stack[-arg_count - 1 :]
        result = self._invoke(callee, args, line)
        if result is not PENDING_CALL:
            self.stack.append(result)

    def _invoke(self, callee: Any, args: list[Any], line: int) -> Any:
        if isinstance(callee, Function):
            self._call_function(callee, args, line)
            return PENDING_CALL
        if isinstance(callee, BoundMethod):
            self._call_function(callee.method, [callee.receiver] + args, line)
            return PENDING_CALL
        if isinstance(callee, Class):
            instance = Instance(callee)
            init = callee.find_method("init")
            if init is None:
                if args:
                    self._error(f"class {callee.name} has no init method", line)
                return instance
            frame = self._make_frame(init, [instance] + args, line)
            frame.is_constructor = True
            frame.constructor_instance = instance
            self.frames.append(frame)
            return PENDING_CALL
        if isinstance(callee, Builtin):
            if callee.arity >= 0 and len(args) != callee.arity:
                self._error(f"{callee.name} expects {callee.arity} arguments, got {len(args)}", line)
            return callee.fn(self, args)
        self._error(f"{type_name(callee)} is not callable", line)
        return None

    def _make_frame(self, function: Function, args: list[Any], line: int) -> CallFrame:
        if len(args) != len(function.param_slots):
            expected = len(function.param_slots) - (1 if len(function.param_slots) == function.arity + 1 else 0)
            self._error(f"{function.name} expects {expected} arguments, got {len(args)}", line)
        slots: list[Any] = [None] * function.slot_count
        for (slot, captured), value in zip(function.param_slots, args):
            slots[slot] = Cell(value) if captured else value
        return CallFrame(function, slots)

    def _call_function(self, function: Function, args: list[Any], line: int) -> None:
        frame = self._make_frame(function, args, line)
        self.frames.append(frame)

    def _get_property(self, target: Any, name: str, line: int) -> Any:
        if isinstance(target, Instance):
            if name in target.fields:
                return target.fields[name]
            method = target.klass.find_method(name)
            if method is not None:
                return BoundMethod(target, method)
            self._error(f"undefined property '{name}'", line)
        if isinstance(target, Class):
            method = target.find_method(name)
            if method is not None:
                return method
            self._error(f"undefined method '{name}'", line)
        self._error("only instances and classes have properties", line)
        return None

    def _get_index(self, container: Any, index: Any, line: int) -> Any:
        if isinstance(container, NimbusList):
            if not isinstance(index, int):
                self._error("list index must be a number", line)
            try:
                return container.items[index]
            except IndexError:
                self._error(f"list index {index} out of bounds", line)
        if isinstance(container, str):
            if not isinstance(index, int):
                self._error("string index must be a number", line)
            try:
                return container[index]
            except IndexError:
                self._error(f"string index {index} out of bounds", line)
        if isinstance(container, NimbusMap):
            return container.entries.get(index, None)
        self._error(f"cannot index {type_name(container)}", line)
        return None

    def _set_index(self, container: Any, index: Any, value: Any, line: int) -> None:
        if isinstance(container, NimbusList):
            if not isinstance(index, int):
                self._error("list index must be a number", line)
            try:
                container.items[index] = value
                return
            except IndexError:
                self._error(f"list index {index} out of bounds", line)
        if isinstance(container, NimbusMap):
            container.entries[index] = value
            return
        self._error(f"cannot index-assign {type_name(container)}", line)

    def _binary(self, opcode: Op, line: int) -> None:
        right = self.stack.pop()
        left = self.stack.pop()
        if opcode == Op.ADD:
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                self.stack.append(left + right)
            elif isinstance(left, str) and isinstance(right, str):
                self.stack.append(left + right)
            elif isinstance(left, NimbusList) and isinstance(right, NimbusList):
                self.stack.append(NimbusList(left.items + right.items))
            else:
                self._error(f"cannot add {type_name(left)} and {type_name(right)}", line)
            return
        if opcode in (Op.SUBTRACT, Op.MULTIPLY, Op.DIVIDE, Op.MODULO):
            self._check_number(left, line, "arithmetic operand")
            self._check_number(right, line, "arithmetic operand")
            if opcode == Op.SUBTRACT:
                self.stack.append(left - right)
            elif opcode == Op.MULTIPLY:
                self.stack.append(left * right)
            elif opcode == Op.DIVIDE:
                if right == 0:
                    self._error("division by zero", line)
                self.stack.append(left / right)
            else:
                if right == 0:
                    self._error("modulo by zero", line)
                self.stack.append(left % right)
            return
        if opcode == Op.EQUAL:
            self.stack.append(self._equals(left, right))
        elif opcode == Op.NOT_EQUAL:
            self.stack.append(not self._equals(left, right))
        elif opcode == Op.GREATER:
            self._comparable(left, right, line)
            self.stack.append(left > right)
        elif opcode == Op.GREATER_EQUAL:
            self._comparable(left, right, line)
            self.stack.append(left >= right)
        elif opcode == Op.LESS:
            self._comparable(left, right, line)
            self.stack.append(left < right)
        elif opcode == Op.LESS_EQUAL:
            self._comparable(left, right, line)
            self.stack.append(left <= right)

    def _equals(self, left: Any, right: Any) -> bool:
        if left is None and right is None:
            return True
        if isinstance(left, (int, float, str, bool)) and isinstance(right, (int, float, str, bool)):
            if isinstance(left, bool) != isinstance(right, bool):
                return False
            return left == right
        return left is right

    def _comparable(self, left: Any, right: Any, line: int) -> None:
        if not (isinstance(left, (int, float, str)) and isinstance(right, (int, float, str))):
            self._error(f"cannot compare {type_name(left)} and {type_name(right)}", line)
        if isinstance(left, str) != isinstance(right, str):
            self._error("cannot compare a string with a number", line)

    def _check_number(self, value: Any, line: int, context: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            self._error(f"{context} requires a number, got {type_name(value)}", line)

    def _error(self, message: str, line: int) -> None:
        raise RuntimeNimbusError(message, line)
