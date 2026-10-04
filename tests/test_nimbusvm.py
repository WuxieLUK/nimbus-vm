from __future__ import annotations

import io
import unittest

from nimbusvm import compile_source, run_source
from nimbusvm.errors import NimbusError
from nimbusvm.parser import Parser
from nimbusvm.tokenizer import Tokenizer


def execute(code: str) -> str:
    output = io.StringIO()
    run_source(code, output=output)
    return output.getvalue()


class LexerTests(unittest.TestCase):
    def test_escapes_and_numbers(self) -> None:
        tokens = Tokenizer('"a\\n" 12 3.5 true').scan_tokens()
        values = [token.literal for token in tokens if token.literal is not None]
        self.assertEqual(values, ["a\n", 12, 3.5])


class ParserTests(unittest.TestCase):
    def test_parser_accepts_program(self) -> None:
        statements = Parser(Tokenizer("let x = 1 + 2;").scan_tokens()).parse()
        self.assertEqual(len(statements), 1)

    def test_parse_error_has_location(self) -> None:
        with self.assertRaises(NimbusError):
            Parser(Tokenizer("let = 1;").scan_tokens()).parse()


class BytecodeTests(unittest.TestCase):
    def test_compile_source(self) -> None:
        function = compile_source("fn add(a, b) { return a + b; } print(add(2, 3));")
        self.assertGreater(len(function.chunk.code), 0)


class ExecutionTests(unittest.TestCase):
    def test_arithmetic(self) -> None:
        self.assertEqual(execute("print(1 + 2 * 3);"), "7\n")

    def test_recursion(self) -> None:
        output = execute(
            "fn fib(n) { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } print(fib(10));"
        )
        self.assertEqual(output, "55\n")

    def test_closures_are_mutable_captures(self) -> None:
        output = execute(
            "let make = fn() { let x = 0; return fn() { x = x + 1; return x; }; };"
            "let next = make(); print(next()); print(next()); print(next());"
        )
        self.assertEqual(output, "1\n2\n3\n")

    def test_nested_closures(self) -> None:
        output = execute(
            "fn outer() { let a = 10; fn mid() { fn inner() { return a + 1; } return inner; } return mid; }"
            "print(outer()()());"
        )
        self.assertEqual(output, "11\n")

    def test_lists_and_maps(self) -> None:
        output = execute(
            'let m = #{"a": 1}; m["b"] = 2; let xs = [1, 2, 3];'
            'print(len(xs), len(m), xs[0], m["b"]);'
        )
        self.assertEqual(output, "3 2 1 2\n")

    def test_for_loop(self) -> None:
        output = execute("let total = 0; for (let x in [1, 2, 3, 4]) { total = total + x; } print(total);")
        self.assertEqual(output, "10\n")

    def test_while_break_continue(self) -> None:
        output = execute(
            "let i = 0; while (i < 10) { i = i + 1; if (i == 2) { continue; } if (i == 4) { break; } print(i); }"
        )
        self.assertEqual(output, "1\n3\n")

    def test_classes_and_inheritance(self) -> None:
        output = execute(
            "class A { init() { this.x = 1; } hello() { return this.x; } }"
            "class B < A { extra() { return this.x + 10; } }"
            "let b = B(); print(b.hello()); print(b.extra());"
        )
        self.assertEqual(output, "1\n11\n")

    def test_this_captured_by_nested_function(self) -> None:
        output = execute(
            "class Counter { init() { this.n = 0; } next() { fn bump() { this.n = this.n + 1; return this.n; } return bump; } }"
            "let c = Counter(); let n = c.next(); print(n()); print(n());"
        )
        self.assertEqual(output, "1\n2\n")

    def test_truthiness_and_logical_operators(self) -> None:
        output = execute('print(false or "ok"); print(true and "yes"); print(not false);')
        self.assertEqual(output, "ok\nyes\ntrue\n")

    def test_string_iteration(self) -> None:
        output = execute('for (let c in "ab") { print(c); }')
        self.assertEqual(output, "a\nb\n")

    def test_captured_loop_variable(self) -> None:
        output = execute(
            "fn make() { let fns = []; for (let x in [1, 2, 3]) { fns = fns + [fn() { return x; }]; } return fns; }"
            "let fns = make(); print(fns[0]()); print(fns[1]()); print(fns[2]());"
        )
        self.assertEqual(output, "1\n2\n3\n")


class ErrorTests(unittest.TestCase):
    def test_undefined_variable(self) -> None:
        with self.assertRaises(NimbusError):
            execute("print(missing);")

    def test_stack_trace_mentions_function(self) -> None:
        try:
            execute("fn boom() { return missing; } boom();")
        except NimbusError as exc:
            self.assertIn("boom", str(exc))
        else:
            self.fail("expected NimbusError")


class GarbageCollectionTests(unittest.TestCase):
    def test_large_allocation_does_not_crash(self) -> None:
        output = execute(
            "fn build(n) { let xs = []; let i = 0; while (i < n) { xs = xs + [i]; i = i + 1; } return xs; }"
            "let xs = build(3000); print(len(xs)); print(xs[2999]);"
        )
        self.assertEqual(output, "3000\n2999\n")


if __name__ == "__main__":
    unittest.main()
