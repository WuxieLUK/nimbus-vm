"""Runtime object model and mark-sweep garbage collector."""

from __future__ import annotations

from typing import Any, Callable


_heap_objects: list["NimbusObject"] = []


class NimbusObject:
    def __init__(self) -> None:
        self.marked = False
        _heap_objects.append(self)

    def refs(self) -> list["NimbusObject"]:
        return []


class NimbusList(NimbusObject):
    def __init__(self, items: list[Any]) -> None:
        super().__init__()
        self.items = items

    def refs(self) -> list[NimbusObject]:
        return [item for item in self.items if isinstance(item, NimbusObject)]


class NimbusMap(NimbusObject):
    def __init__(self, entries: dict[Any, Any]) -> None:
        super().__init__()
        self.entries = entries

    def refs(self) -> list[NimbusObject]:
        refs = [key for key in self.entries if isinstance(key, NimbusObject)]
        refs.extend(value for value in self.entries.values() if isinstance(value, NimbusObject))
        return refs


class Cell(NimbusObject):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value

    def refs(self) -> list[NimbusObject]:
        return [self.value] if isinstance(self.value, NimbusObject) else []


class Function(NimbusObject):
    def __init__(
        self,
        chunk,
        name: str,
        arity: int,
        slot_count: int,
        param_slots: list[tuple[int, bool]],
        upvalues: list[Cell],
    ) -> None:
        super().__init__()
        self.chunk = chunk
        self.name = name
        self.arity = arity
        self.slot_count = slot_count
        self.param_slots = param_slots
        self.upvalues = upvalues

    def refs(self) -> list[NimbusObject]:
        refs: list[NimbusObject] = list(self.upvalues)
        refs.extend(constant for constant in self.chunk.constants if isinstance(constant, NimbusObject))
        return refs


class Class(NimbusObject):
    def __init__(self, name: str, superclass: "Class | None" = None) -> None:
        super().__init__()
        self.name = name
        self.superclass = superclass
        self.methods: dict[str, Function] = {}

    def find_method(self, name: str) -> Function | None:
        current: Class | None = self
        while current is not None:
            if name in current.methods:
                return current.methods[name]
            current = current.superclass
        return None

    def refs(self) -> list[NimbusObject]:
        refs = list(self.methods.values())
        if self.superclass is not None:
            refs.append(self.superclass)
        return refs


class Instance(NimbusObject):
    def __init__(self, klass: Class) -> None:
        super().__init__()
        self.klass = klass
        self.fields: dict[str, Any] = {}

    def refs(self) -> list[NimbusObject]:
        refs = [self.klass]
        refs.extend(value for value in self.fields.values() if isinstance(value, NimbusObject))
        return refs


class BoundMethod(NimbusObject):
    def __init__(self, receiver: Instance, method: Function) -> None:
        super().__init__()
        self.receiver = receiver
        self.method = method

    def refs(self) -> list[NimbusObject]:
        return [self.receiver, self.method]


class Builtin(NimbusObject):
    def __init__(self, name: str, arity: int, fn: Callable[["VM"], Any]) -> None:
        super().__init__()
        self.name = name
        self.arity = arity
        self.fn = fn


def heap_size() -> int:
    return len(_heap_objects)


def collect_garbage(roots: list[Any]) -> None:
    stack = list(roots)
    while stack:
        obj = stack.pop()
        if isinstance(obj, NimbusObject) and not obj.marked:
            obj.marked = True
            stack.extend(obj.refs())
    retained: list[NimbusObject] = []
    for obj in _heap_objects:
        if obj.marked:
            obj.marked = False
            retained.append(obj)
    _heap_objects[:] = retained


def is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, NimbusList):
        return len(value.items) > 0
    if isinstance(value, NimbusMap):
        return len(value.entries) > 0
    return True


def type_name(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True or value is False:
        return "bool"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, NimbusList):
        return "list"
    if isinstance(value, NimbusMap):
        return "map"
    if isinstance(value, BoundMethod):
        return "bound_method"
    if isinstance(value, Instance):
        return value.klass.name
    if isinstance(value, Class):
        return f"<class {value.name}>"
    if isinstance(value, Function):
        return f"<fn {value.name}>"
    if isinstance(value, Builtin):
        return f"<builtin {value.name}>"
    if isinstance(value, Cell):
        return "cell"
    return type(value).__name__
