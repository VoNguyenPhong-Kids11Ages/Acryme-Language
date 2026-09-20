"""Transpile an Acryme AST into Python source text."""

from . import ast_nodes as A
from .lexer import RENAME_NAMES

INDENT_UNIT = "    "  # 4 spaces; Python only needs *consistent* indentation.


class PyGen:
    def __init__(self):
        self.lines = []

    def generate(self, module: A.Module) -> str:
        self._block(module.body, 0)
        if not self.lines:
            self.lines.append("pass")
        return "\n".join(self.lines) + "\n"

    # -- statements ------------------------------------------------------
    def _block(self, stmts, depth):
        if not stmts:
            self.lines.append(INDENT_UNIT * depth + "pass")
            return
        for s in stmts:
            self._stmt(s, depth)

    def _emit(self, depth, text):
        self.lines.append(INDENT_UNIT * depth + text)

    def _stmt(self, node, depth):
        if isinstance(node, A.Assign):
            targets = " = ".join(self._expr(t) for t in node.targets)
            self._emit(depth, f"{targets} = {self._expr(node.value)}")
        elif isinstance(node, A.AugAssign):
            self._emit(depth, f"{self._expr(node.target)} {node.op} {self._expr(node.value)}")
        elif isinstance(node, A.ExprStmt):
            self._emit(depth, self._expr(node.value))
        elif isinstance(node, A.If):
            self._emit(depth, f"if {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
            self._orelse(node.orelse, depth)
        elif isinstance(node, A.While):
            self._emit(depth, f"while {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.For):
            targets = ", ".join(node.targets)
            self._emit(depth, f"for {targets} in {self._expr(node.iter)}:")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.FunctionDef):
            params = self._params(node)
            self._emit(depth, f"def {node.name}({params}):")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.Return):
            if node.value is None:
                self._emit(depth, "return")
            else:
                self._emit(depth, f"return {self._expr(node.value)}")
        elif isinstance(node, A.ClassDef):
            bases = ", ".join(self._expr(b) for b in node.bases)
            head = f"class {node.name}({bases}):" if bases else f"class {node.name}:"
            self._emit(depth, head)
            self._block(node.body, depth + 1)
        elif isinstance(node, A.Import):
            self._emit(depth, "import " + ", ".join(node.names))
        elif isinstance(node, A.ImportFrom):
            self._emit(depth, f"from {node.module} import " + ", ".join(node.names))
        elif isinstance(node, A.Pass):
            self._emit(depth, "pass")
        else:
            raise TypeError(f"codegen: unhandled statement node {type(node).__name__}")

    def _orelse(self, orelse, depth):
        if not orelse:
            return
        # A chain of `el`s is represented as a single nested If marked is_elif;
        # a plain nested `i` as the sole statement of an `els:` block is not.
        if len(orelse) == 1 and isinstance(orelse[0], A.If) and getattr(orelse[0], "is_elif", False):
            node = orelse[0]
            self._emit(depth, f"elif {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
            self._orelse(node.orelse, depth)
        else:
            self._emit(depth, "else:")
            self._block(orelse, depth + 1)

    def _params(self, fn: A.FunctionDef):
        defaults = dict(fn.defaults)
        parts = []
        for p in fn.params:
            if p in defaults:
                parts.append(f"{p}={self._expr(defaults[p])}")
            else:
                parts.append(p)
        return ", ".join(parts)

    # -- expressions -----------------------------------------------------
    def _expr(self, node):
        if isinstance(node, A.Name):
            return RENAME_NAMES.get(node.id, node.id)
        if isinstance(node, A.Num):
            return node.value
        if isinstance(node, A.Str):
            return node.value
        if isinstance(node, A.BinOp):
            return f"({self._expr(node.left)} {node.op} {self._expr(node.right)})"
        if isinstance(node, A.BoolOp):
            joiner = f" {node.op} "
            return "(" + joiner.join(self._expr(v) for v in node.values) + ")"
        if isinstance(node, A.UnaryOp):
            if node.op == "not":
                return f"(not {self._expr(node.operand)})"
            return f"({node.op}{self._expr(node.operand)})"
        if isinstance(node, A.Compare):
            parts = [self._expr(node.left)]
            for op, comp in zip(node.ops, node.comparators):
                parts.append(op)
                parts.append(self._expr(comp))
            return "(" + " ".join(parts) + ")"
        if isinstance(node, A.Call):
            args = [self._expr(a) for a in node.args]
            args += [f"{name}={self._expr(v)}" for name, v in node.kwargs]
            return f"{self._expr(node.func)}({', '.join(args)})"
        if isinstance(node, A.Attribute):
            return f"{self._expr(node.value)}.{node.attr}"
        if isinstance(node, A.Subscript):
            return f"{self._expr(node.value)}[{self._expr(node.index)}]"
        if isinstance(node, A.ListLit):
            return "[" + ", ".join(self._expr(e) for e in node.elts) + "]"
        if isinstance(node, A.TupleLit):
            elts = [self._expr(e) for e in node.elts]
            if len(elts) == 1:
                return f"({elts[0]},)"
            return "(" + ", ".join(elts) + ")"
        if isinstance(node, A.DictLit):
            pairs = [f"{self._expr(k)}: {self._expr(v)}" for k, v in zip(node.keys, node.values)]
            return "{" + ", ".join(pairs) + "}"
        raise TypeError(f"codegen: unhandled expression node {type(node).__name__}")


def to_python(module: A.Module) -> str:
    return PyGen().generate(module)
