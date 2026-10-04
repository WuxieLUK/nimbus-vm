"""Tiny benchmark runner: fib and loop allocations."""

from __future__ import annotations

import time

from nimbusvm import run_source


def time_source(name: str, source: str) -> None:
    start = time.perf_counter()
    run_source(source)
    elapsed = time.perf_counter() - start
    print(f"{name:<24} {elapsed * 1000:8.2f} ms")


time_source(
    "fib(26) recursive",
    "fn fib(n) { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } fib(26);",
)
time_source(
    "loop 200_000 iterations",
    "let i = 0; let s = 0; while (i < 200000) { s = s + i; i = i + 1; }",
)
time_source(
    "build 2_000 lists",
    "fn build(n) { let xs = []; let i = 0; while (i < n) { xs = xs + [i]; i = i + 1; } return xs; } build(2000);",
)
