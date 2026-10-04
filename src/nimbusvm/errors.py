"""Error types with source locations."""

from __future__ import annotations


class NimbusError(Exception):
    def __init__(self, message: str, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def format(self) -> str:
        if self.line is not None:
            location = f"[line {self.line}" + (f", col {self.column}]" if self.column is not None else "]")
            return f"{location} {self.message}"
        return self.message


class LexError(NimbusError):
    pass


class ParseError(NimbusError):
    pass


class ResolveError(NimbusError):
    pass


class CompileError(NimbusError):
    pass


class RuntimeNimbusError(NimbusError):
    pass
