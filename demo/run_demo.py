"""Terminal demo for nimbus-vm.

Run from the repository root:
    python demo/run_demo.py

Add ``--fast`` to disable the short pauses between sections.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nimbusvm import compile_source, run_source
from nimbusvm.disassembler import disassemble
from nimbusvm.errors import NimbusError
from nimbusvm.objects import heap_size
from nimbusvm.parser import Parser
from nimbusvm.tokenizer import Tokenizer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def banner(text: str) -> None:
    print()
    print("=" * 64)
    print(f"  {text}")
    print("=" * 64)


def show_code(code: str) -> None:
    print()
    for line in code.strip().splitlines():
        print(f"    {line}")
    print()


def execute(label: str, code: str) -> None:
    print(f"  > {label}")
    show_code(code)
    output = io.StringIO()
    run_source(code, output=output)
    text = output.getvalue()
    for line in text.rstrip("\n").splitlines():
        print(f"  [ok] {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the nimbus-vm terminal demo")
    parser.add_argument("--fast", action="store_true", help="disable pauses")
    args = parser.parse_args()
    delay = 0.0 if args.fast else 0.45

    banner("nimbus-vm · compiler + bytecode VM demo")
    print("  从源码到字节码，再到垃圾回收，全部在标准库内完成。")

    banner("1. 词法分析")
    code = 'let answer = 40 + 2; print(answer);'
    show_code(code)
    tokens = Tokenizer(code).scan_tokens()
    print("  tokens:")
    for token in tokens:
        literal = f" literal={token.literal!r}" if token.literal is not None else ""
        print(f"    {token.type.name:<12} {token.lexeme!r}{literal}")

    banner("2. 语法树")
    code = "let score = 90 * 2 + 7;"
    show_code(code)
    statements = Parser(Tokenizer(code).scan_tokens()).parse()
    print(f"  top-level statements: {len(statements)}")
    print(f"  root node type: {type(statements[0]).__name__}")
    time.sleep(delay)

    banner("3. 字节码")
    code = "fn fib(n) { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } print(fib(10));"
    show_code(code)
    function = compile_source(code)
    lines = disassemble(function).splitlines()
    for line in lines[:14]:
        print(f"    {line}")
    print("    ...")
    time.sleep(delay)

    banner("4. 栈式 VM 执行")
    execute("递归调用", "fn fib(n) { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } print(fib(15));")
    time.sleep(delay)

    banner("5. 闭包捕获")
    execute(
        "可变闭包状态",
        "fn make_counter() {\n"
        "  let n = 0;\n"
        "  return fn() { n = n + 1; return n; };\n"
        "}\n"
        "let next = make_counter();\n"
        "print(next()); print(next()); print(next());",
    )
    time.sleep(delay)

    banner("6. 类与继承")
    execute(
        "面向对象",
        'class Animal {\n'
        '  init(name) { this.name = name; }\n'
        '}\n'
        'class Dog < Animal {\n'
        '  speak() { return this.name + " says woof"; }\n'
        '}\n'
        'let dog = Dog("Rex");\n'
        'print(dog.speak());',
    )
    time.sleep(delay)

    banner("7. 数据结构与内置函数")
    execute(
        "list / map / 循环",
        'let m = #{"a": 1, "b": 2};\n'
        'm["c"] = 3;\n'
        'let total = 0;\n'
        'for (let v in values(m)) { total = total + v; }\n'
        'print("sum =", total, "keys =", keys(m));',
    )
    time.sleep(delay)

    banner("8. 标记-清扫 GC")
    code = (
        "fn build(n) {\n"
        "  let xs = [];\n"
        "  let i = 0;\n"
        "  while (i < n) { xs = xs + [i]; i = i + 1; }\n"
        "  return xs;\n"
        "}\n"
        "let data = build(3000);\n"
        "print(len(data), data[2999]);"
    )
    show_code(code)
    before = heap_size()
    output = io.StringIO()
    run_source(code, output=output)
    after = heap_size()
    print(f"  [ok] {output.getvalue().strip()}")
    print(f"  heap: {before} objects allocated, {after} live after collection")
    time.sleep(delay)

    banner("9. 错误诊断")
    code = "fn outer() { fn inner() { return missing; } inner(); } outer();"
    show_code(code)
    try:
        run_source(code)
    except NimbusError as exc:
        print("  [err] 运行时错误 + 调用栈：")
        for line in str(exc).splitlines():
            print(f"    {line}")

    banner("done")
    print("  更多示例： examples/*.nb")
    print("  REPL：     python -m nimbusvm repl")
    print("  测试：     python -m unittest discover -s tests -v")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
