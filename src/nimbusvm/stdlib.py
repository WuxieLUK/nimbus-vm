"""Native functions exposed to Nimbus programs."""

from __future__ import annotations

import time

from .errors import RuntimeNimbusError
from .objects import Builtin, NimbusList, NimbusMap, is_truthy, type_name


class ExitProgram(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _check_arity(name: str, expected: int, args: list) -> None:
    if len(args) != expected:
        raise RuntimeNimbusError(f"{name} expects {expected} arguments, got {len(args)}")


def _list(value) -> NimbusList:
    if not isinstance(value, NimbusList):
        raise RuntimeNimbusError(f"expected a list, got {type_name(value)}")
    return value


def _map(value) -> NimbusMap:
    if not isinstance(value, NimbusMap):
        raise RuntimeNimbusError(f"expected a map, got {type_name(value)}")
    return value


def install_builtins(vm) -> dict[str, Builtin]:
    def print_fn(_vm, args):
        _vm.write(" ".join(_vm.stringify(arg) for arg in args) + "\n")
        return None

    def len_fn(_vm, args):
        _check_arity("len", 1, args)
        value = args[0]
        if isinstance(value, str):
            return len(value)
        if isinstance(value, NimbusList):
            return len(value.items)
        if isinstance(value, NimbusMap):
            return len(value.entries)
        raise RuntimeNimbusError(f"len() does not support {type_name(value)}")

    def str_fn(_vm, args):
        _check_arity("str", 1, args)
        return _vm.stringify(args[0])

    def type_fn(_vm, args):
        _check_arity("type", 1, args)
        return type_name(args[0])

    def int_fn(_vm, args):
        _check_arity("int", 1, args)
        value = args[0]
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
        raise RuntimeNimbusError(f"cannot convert {type_name(value)} to int")

    def float_fn(_vm, args):
        _check_arity("float", 1, args)
        value = args[0]
        if isinstance(value, (int, float, str)):
            return float(value)
        raise RuntimeNimbusError(f"cannot convert {type_name(value)} to float")

    def clock_fn(_vm, args):
        _check_arity("clock", 0, args)
        return time.perf_counter()

    def push_fn(_vm, args):
        _check_arity("push", 2, args)
        target = _list(args[0])
        target.items.append(args[1])
        return target

    def pop_fn(_vm, args):
        _check_arity("pop", 1, args)
        target = _list(args[0])
        if not target.items:
            return None
        return target.items.pop()

    def get_fn(_vm, args):
        _check_arity("get", 2, args)
        container, key = args
        if isinstance(container, NimbusList) or isinstance(container, str):
            if not isinstance(key, int):
                raise RuntimeNimbusError("list/string index must be a number")
            index = int(key)
            length = len(container.items) if isinstance(container, NimbusList) else len(container)
            if index < 0:
                index += length
            if index < 0 or index >= length:
                raise RuntimeNimbusError(f"index {key} out of bounds")
            return container.items[index] if isinstance(container, NimbusList) else container[index]
        if isinstance(container, NimbusMap):
            if key not in container.entries:
                return None
            return container.entries[key]
        raise RuntimeNimbusError(f"get() does not support {type_name(container)}")

    def set_fn(_vm, args):
        _check_arity("set", 3, args)
        container, key, value = args
        if isinstance(container, NimbusList):
            if not isinstance(key, int):
                raise RuntimeNimbusError("list index must be a number")
            index = int(key)
            length = len(container.items)
            if index < 0:
                index += length
            if index < 0 or index >= length:
                raise RuntimeNimbusError(f"index {key} out of bounds")
            container.items[index] = value
            return value
        if isinstance(container, NimbusMap):
            container.entries[key] = value
            return value
        raise RuntimeNimbusError(f"set() does not support {type_name(container)}")

    def keys_fn(_vm, args):
        _check_arity("keys", 1, args)
        return NimbusList(list(_map(args[0]).entries.keys()))

    def values_fn(_vm, args):
        _check_arity("values", 1, args)
        return NimbusList(list(_map(args[0]).entries.values()))

    def has_fn(_vm, args):
        _check_arity("has", 2, args)
        return args[1] in _map(args[0]).entries

    def range_fn(_vm, args):
        _check_arity("range", 1, args)
        if not isinstance(args[0], int) or args[0] < 0:
            raise RuntimeNimbusError("range() expects a non-negative integer")
        return NimbusList(list(range(args[0])))

    def read_line_fn(_vm, args):
        _check_arity("read_line", 0, args)
        line = _vm.read_input()
        return line.rstrip("\n")

    def exit_fn(_vm, args):
        _check_arity("exit", 1, args)
        raise ExitProgram(int(args[0]))

    def chr_fn(_vm, args):
        _check_arity("chr", 1, args)
        return chr(int(args[0]))

    def ord_fn(_vm, args):
        _check_arity("ord", 1, args)
        if not isinstance(args[0], str) or len(args[0]) != 1:
            raise RuntimeNimbusError("ord() expects a single-character string")
        return ord(args[0])

    def abs_fn(_vm, args):
        _check_arity("abs", 1, args)
        return abs(args[0])

    def min_fn(_vm, args):
        _check_arity("min", 2, args)
        return args[0] if args[0] < args[1] else args[1]

    def max_fn(_vm, args):
        _check_arity("max", 2, args)
        return args[0] if args[0] > args[1] else args[1]

    return {
        "print": Builtin("print", -1, print_fn),
        "len": Builtin("len", 1, len_fn),
        "str": Builtin("str", 1, str_fn),
        "type": Builtin("type", 1, type_fn),
        "int": Builtin("int", 1, int_fn),
        "float": Builtin("float", 1, float_fn),
        "clock": Builtin("clock", 0, clock_fn),
        "push": Builtin("push", 2, push_fn),
        "pop": Builtin("pop", 1, pop_fn),
        "get": Builtin("get", 2, get_fn),
        "set": Builtin("set", 3, set_fn),
        "keys": Builtin("keys", 1, keys_fn),
        "values": Builtin("values", 1, values_fn),
        "has": Builtin("has", 2, has_fn),
        "range": Builtin("range", 1, range_fn),
        "read_line": Builtin("read_line", 0, read_line_fn),
        "exit": Builtin("exit", 1, exit_fn),
        "chr": Builtin("chr", 1, chr_fn),
        "ord": Builtin("ord", 1, ord_fn),
        "abs": Builtin("abs", 1, abs_fn),
        "min": Builtin("min", 2, min_fn),
        "max": Builtin("max", 2, max_fn),
    }
