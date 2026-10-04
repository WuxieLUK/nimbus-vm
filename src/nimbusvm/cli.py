"""Command-line interface for nimbus-vm."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, compile_source, run_source
from .disassembler import disassemble
from .errors import NimbusError
from .stdlib import ExitProgram


def _read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _repl() -> int:
    print(f"Nimbus REPL {__version__} (type 'exit' to quit)")
    from .tokenizer import Tokenizer
    from .parser import Parser
    from .vm import VM

    vm = VM()
    buffer = ""
    while True:
        prompt = "nimbus> " if not buffer else ".....> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if buffer:
            buffer += "\n" + line
        else:
            buffer = line
        if buffer.strip() in ("exit", "quit"):
            return 0
        try:
            tokens = Tokenizer(buffer).scan_tokens()
            statements = Parser(tokens).parse()
            vm.interpret(statements)
            buffer = ""
        except NimbusError as exc:
            print(exc.format(), file=sys.stderr)
            buffer = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nimbus-vm",
        description="A bytecode compiler and virtual machine for the Nimbus language.",
    )
    parser.add_argument("--version", action="version", version=f"nimbus-vm {__version__}")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute a Nimbus source file")
    run_parser.add_argument("file")

    sub.add_parser("repl", help="Start the interactive REPL")

    dis_parser = sub.add_parser("disassemble", help="Show bytecode for a source file")
    dis_parser.add_argument("file")

    compile_parser = sub.add_parser("compile", help="Compile without executing")
    compile_parser.add_argument("file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "run":
            run_source(_read_file(args.file), args.file)
        elif args.command == "repl":
            return _repl()
        elif args.command == "disassemble":
            function = compile_source(_read_file(args.file), args.file)
            print(disassemble(function))
        elif args.command == "compile":
            compile_source(_read_file(args.file), args.file)
            print(f"compiled {args.file}")
        return 0
    except ExitProgram as exc:
        return exc.code
    except NimbusError as exc:
        print(exc.format(), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
