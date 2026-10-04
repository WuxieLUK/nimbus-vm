# nimbus-vm

一个 **从零实现编译器 + 字节码虚拟机** 的项目，语言名为 **Nimbus**。
纯 Python 标准库、**零第三方运行时依赖**：手写词法分析器、递归下降 + Pratt 解析器、语义解析器、字节码编译器、栈式虚拟机，以及 **标记-清扫（mark-sweep）垃圾回收器**。

> 与 [nimbus-kv](https://github.com/WuxieLUK/nimbus-kv)、[nimbus-git](https://github.com/WuxieLUK/nimbus-git) 同属 Nimbus 系统系列。

## 为什么具备获奖竞争力

- **完整编译流水线**：`source -> tokens -> AST -> resolved AST -> bytecode -> VM`，不是玩具解释器。
- **真正的字节码 VM**：46 个指令的栈式虚拟机，支持闭包、upvalue、短路的 `and/or`、`break/continue`、循环、方法调用。
- **词法作用域 + 可变闭包捕获**：被内层函数捕获的局部变量自动升级为 Cell，支持多层闭包和 `this` 捕获。
- **类与单继承**：`class`、`init`、`this`、方法继承，实例字段与方法分派。
- **自研 GC**：可触达性分析 + 标记-清扫，支持高分配压力下的自动回收。
- **清晰的错误诊断**：编译期带行列号；运行期异常带函数调用栈。
- **零依赖可复现**：任何有 Python 3.10+ 的机器直接跑。
- **可测试**：18 个单元测试覆盖词法、解析、编译、执行、GC 和错误路径。

## 架构

```
                         source.nb
                            │
                   ┌────────▼────────┐
                   │    tokenizer    │  tokens.py / tokenizer.py
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │     parser      │  ast.py / parser.py
                   └────────┬────────┘
                            │  AST
                   ┌────────▼────────┐
                   │    resolver     │  scopes / upvalues / captured locals
                   └────────┬────────┘
                            │  resolved AST
                   ┌────────▼────────┐
                   │    compiler     │  chunk.py / compiler.py
                   └────────┬────────┘
                            │  bytecode
                   ┌────────▼────────┐
                   │       VM        │  vm.py / objects.py
                   │  mark-sweep GC  │
                   └─────────────────┘
```

## 语言速览

```text
// 变量、函数、递归
let name = "Nimbus";

fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}

// 闭包捕获
fn make_counter() {
  let count = 0;
  return fn() { count = count + 1; return count; };
}

// 类与继承
class Animal {
  init(name) { this.name = name; }
}
class Dog < Animal {
  speak() { return this.name + " says woof"; }
}

let dog = Dog("Rex");
print(dog.speak());
```

支持的类型：`nil`、`bool`、`number`、`string`、`list`、`map`、`fn`、`class`、`instance`。

Map 字面量使用 `#{}`：

```text
let scores = #{"alice": 92, "bob": 85};
scores["carol"] = 97;
```

## 快速开始

```bash
git clone https://github.com/WuxieLUK/nimbus-vm.git
cd nimbus-vm
python -m nimbusvm run examples/fib.nb
python -m nimbusvm repl
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m nimbusvm run examples\fib.nb
python -m nimbusvm disassemble examples\fib.nb
```

## 命令

```text
nimbus-vm run FILE          # 执行源码
nimbus-vm repl              # 交互式 REPL
nimbus-vm disassemble FILE  # 查看字节码
nimbus-vm compile FILE      # 只编译不执行
```

## 字节码示例

`python -m nimbusvm disassemble examples/fib.nb` 会输出类似：

```text
== function fib arity=1 slots=1 ==
0000  GET_LOCAL            0                ; line 2
0002  CONSTANT             2                ; line 2
0004  LESS                                  ; line 2
...
```

## 内置函数

`print`、`len`、`str`、`type`、`int`、`float`、`clock`、`push`、`pop`、`get`、`set`、`keys`、`values`、`has`、`range`、`read_line`、`exit`、`chr`、`ord`、`abs`、`min`、`max`。

## 测试与基准

```bash
export PYTHONPATH=src
python -m unittest discover -s tests -v
python benchmarks/run_benchmarks.py
```

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `src/nimbusvm/tokenizer.py` | 手写词法分析器 |
| `src/nimbusvm/parser.py` | 递归下降 + Pratt 解析器 |
| `src/nimbusvm/resolver.py` | 作用域、闭包捕获与 upvalue 解析 |
| `src/nimbusvm/compiler.py` | AST 到字节码 |
| `src/nimbusvm/chunk.py` | 字节码与操作数格式 |
| `src/nimbusvm/vm.py` | 栈式 VM、调用帧、错误栈追踪 |
| `src/nimbusvm/objects.py` | 运行时对象与标记-清扫 GC |
| `src/nimbusvm/stdlib.py` | 内置函数 |
| `src/nimbusvm/disassembler.py` | 字节码反汇编器 |

## Roadmap

- [ ] `super` 调用与更完整的继承
- [ ] 常量折叠与窥孔优化
- [ ] 分代 GC 或增量标记
- [ ] 模块/导入系统
- [ ] 原生编译到 `.nbc` 字节码文件
- [ ] 更丰富的标准库与异常系统

## License

MIT
