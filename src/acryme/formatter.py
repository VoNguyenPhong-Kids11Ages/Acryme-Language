"""Pretty-print an Acryme AST back into canonical Acryme source.

Used by `a fmt`. Re-derives formatting only (2-space indent); the AST
does not retain comments, so a formatted file will not keep them yet.
"""

from . import ast_nodes as A

INDENT_UNIT = "  "  # 2 spaces, per the language spec's default formatting.
UNARY_ACRYME = {"not": "!"}
BOOL_ACRYME = {"and": "&", "or": "|"}


class AcrymeGen:
    def __init__(self):
        self.lines = []

    def generate(self, module: A.Module) -> str:
        self._block(module.body, 0)
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def _block(self, stmts, depth):
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
            self._emit(depth, f"i {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
            self._orelse(node.orelse, depth)
        elif isinstance(node, A.While):
            self._emit(depth, f"wh {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.For):
            targets = ", ".join(node.targets)
            self._emit(depth, f"fr {targets} n {self._expr(node.iter)}:")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.FunctionDef):
            defaults = dict(node.defaults)
            parts = [f"{p}={self._expr(defaults[p])}" if p in defaults else p for p in node.params]
            self._emit(depth, f"fn {node.name}({', '.join(parts)}):")
            self._block(node.body, depth + 1)
        elif isinstance(node, A.Return):
            self._emit(depth, "ret" if node.value is None else f"ret {self._expr(node.value)}")
        elif isinstance(node, A.ClassDef):
            bases = ", ".join(self._expr(b) for b in node.bases)
            head = f"cls {node.name}({bases}):" if bases else f"cls {node.name}:"
            self._emit(depth, head)
            self._block(node.body, depth + 1)
        elif isinstance(node, A.Import):
            self._emit(depth, "imp " + ", ".join(node.names))
        elif isinstance(node, A.ImportFrom):
            self._emit(depth, f"frm {node.module} imp " + ", ".join(node.names))
        else:
            raise TypeError(f"formatter: unhandled statement {type(node).__name__}")

    def _orelse(self, orelse, depth):
        if not orelse:
            return
        if len(orelse) == 1 and isinstance(orelse[0], A.If) and getattr(orelse[0], "is_elif", False):
            node = orelse[0]
            self._emit(depth, f"el {self._expr(node.test)}:")
            self._block(node.body, depth + 1)
            self._orelse(node.orelse, depth)
        else:
            self._emit(depth, "els:")
            self._block(orelse, depth + 1)

    def _expr(self, node):
        if isinstance(node, A.Name):
            return node.id
        if isinstance(node, A.Num):
            return node.value
        if isinstance(node, A.Str):
            return node.value
        if isinstance(node, A.BinOp):
            return f"({self._expr(node.left)} {node.op} {self._expr(node.right)})"
        if isinstance(node, A.BoolOp):
            sym = BOOL_ACRYME[node.op]
            return "(" + f" {sym} ".join(self._expr(v) for v in node.values) + ")"
        if isinstance(node, A.UnaryOp):
            if node.op in UNARY_ACRYME:
                return f"({UNARY_ACRYME[node.op]}{self._expr(node.operand)})"
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
        raise TypeError(f"formatter: unhandled expression {type(node).__name__}")


def to_acryme(module: A.Module) -> str:
    return AcrymeGen().generate(module)
