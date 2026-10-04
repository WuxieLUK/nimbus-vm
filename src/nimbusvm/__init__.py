"""nimbus-vm: a bytecode VM and compiler for the Nimbus language."""

__version__ = "0.1.0"


def run_source(source: str, filename: str = "<script>", output=None, input_func=None):
    """Compile and execute Nimbus source code, returning the VM."""
    from .tokenizer import Tokenizer
    from .parser import Parser
    from .vm import VM

    tokens = Tokenizer(source).scan_tokens()
    statements = Parser(tokens).parse()
    vm = VM(output=output, input_func=input_func)
    vm.interpret(statements)
    return vm


def compile_source(source: str, filename: str = "<script>"):
    """Compile Nimbus source to a top-level Function object."""
    from . import ast
    from .compiler import FunctionCompiler
    from .parser import Parser
    from .resolver import Resolver
    from .tokenizer import Tokenizer

    statements = Parser(Tokenizer(source).scan_tokens()).parse()
    Resolver().resolve(statements)
    synthetic = ast.FunctionExpr(params=[], body=statements)
    synthetic.slot_count = 0
    synthetic.param_slots = []
    synthetic.upvalues = []
    synthetic.is_method = False
    return FunctionCompiler(synthetic, filename).compile()
