"""AST node types for Acryme.

Plain, dependency-free classes (no dataclass requirement) so this stays
readable and easy to extend in later versions.
"""


class Node:
    _fields = ()

    def __init__(self, *args, line=0, col=0):
        for name, val in zip(self._fields, args):
            setattr(self, name, val)
        self.line = line
        self.col = col

    def __repr__(self):
        fields = ", ".join(f"{f}={getattr(self, f)!r}" for f in self._fields)
        return f"{type(self).__name__}({fields})"


class Module(Node):
    _fields = ("body",)


# -- statements ------------------------------------------------------------
class Assign(Node):
    _fields = ("targets", "value")


class AugAssign(Node):
    _fields = ("target", "op", "value")


class ExprStmt(Node):
    _fields = ("value",)


class If(Node):
    _fields = ("test", "body", "orelse")


class While(Node):
    _fields = ("test", "body")


class For(Node):
    _fields = ("targets", "iter", "body")


class FunctionDef(Node):
    _fields = ("name", "params", "defaults", "body")


class Return(Node):
    _fields = ("value",)


class ClassDef(Node):
    _fields = ("name", "bases", "body")


class Import(Node):
    _fields = ("names",)


class ImportFrom(Node):
    _fields = ("module", "names")


class Pass(Node):
    _fields = ()


# -- expressions -------------------------------------------------------
class BinOp(Node):
    _fields = ("left", "op", "right")


class BoolOp(Node):
    _fields = ("op", "values")  # op: 'and' | 'or'


class UnaryOp(Node):
    _fields = ("op", "operand")


class Compare(Node):
    _fields = ("left", "ops", "comparators")


class Call(Node):
    _fields = ("func", "args", "kwargs")  # kwargs: list of (name, value)


class Attribute(Node):
    _fields = ("value", "attr")


class Subscript(Node):
    _fields = ("value", "index")


class Name(Node):
    _fields = ("id",)


class Num(Node):
    _fields = ("value",)


class Str(Node):
    _fields = ("value",)  # raw token text, quotes included


class ListLit(Node):
    _fields = ("elts",)


class TupleLit(Node):
    _fields = ("elts",)


class DictLit(Node):
    _fields = ("keys", "values")
