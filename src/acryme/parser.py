"""Acryme parser: token stream -> AST.

A small recursive-descent parser. Acryme's grammar is Python's grammar
with renamed keywords/operators, so the shape below mirrors Python's
statement/expression grammar closely.
"""

from . import ast_nodes as A
from .errors import AcrymeSyntaxError

COMPARE_OPS = {"==", "!=", ">", "<", ">=", "<="}
AUG_OPS = {"+=", "-=", "*=", "/=", "//=", "%=", "**="}


class Parser:
    def __init__(self, tokens, filename="<string>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0

    # -- token helpers -------------------------------------------------
    def _cur(self):
        return self.tokens[self.pos]

    def _peek_type(self, offset=0):
        i = self.pos + offset
        if i < len(self.tokens):
            return self.tokens[i].type
        return "ENDMARKER"

    def _at(self, *types):
        return self._cur().type in types

    def _at_kw(self, value):
        """Is the current token a NAME whose text is this soft keyword?"""
        tok = self._cur()
        return tok.type == "NAME" and tok.value == value

    def _expect_kw(self, value, msg=None):
        tok = self._cur()
        if not (tok.type == "NAME" and tok.value == value):
            raise AcrymeSyntaxError(self.filename, tok.line, tok.col,
                                     msg or f"expected {value!r}, got {tok.value!r}")
        return self._advance()

    def _advance(self):
        tok = self.tokens[self.pos]
        if tok.type != "ENDMARKER":
            self.pos += 1
        return tok

    def _expect(self, type_, msg=None):
        tok = self._cur()
        if tok.type != type_:
            raise AcrymeSyntaxError(self.filename, tok.line, tok.col,
                                     msg or f"expected {type_!r}, got {tok.value!r}")
        return self._advance()

    def _error(self, msg, tok=None):
        tok = tok or self._cur()
        raise AcrymeSyntaxError(self.filename, tok.line, tok.col, msg)

    # -- entry -----------------------------------------------------------
    def parse_module(self):
        body = []
        while not self._at("ENDMARKER"):
            if self._at("NEWLINE"):
                self._advance()
                continue
            body.append(self._statement())
        return A.Module(body, line=1, col=1)

    # -- statements -----------------------------------------------------
    def _statement(self):
        if self._at_kw("i"):
            return self._if_stmt()
        if self._at_kw("wh"):
            return self._while_stmt()
        if self._at_kw("fr"):
            return self._for_stmt()
        if self._at_kw("fn"):
            return self._funcdef()
        if self._at_kw("cls"):
            return self._classdef()
        return self._simple_stmt()

    def _suite(self):
        """':' already consumed by caller. Returns list of statements."""
        if self._at("NEWLINE"):
            self._advance()
            self._expect("INDENT", "expected an indented block")
            stmts = []
            while not self._at("DEDENT", "ENDMARKER"):
                if self._at("NEWLINE"):
                    self._advance()
                    continue
                stmts.append(self._statement())
            self._expect("DEDENT")
            return stmts
        # one-liner: `i x: pnt(x)`
        stmt = self._small_stmt()
        self._end_simple_stmt()
        return [stmt]

    def _if_stmt(self):
        tok = self._advance()  # 'i'
        test = self._expr()
        self._expect("COLON", "expected ':'")
        body = self._suite()
        orelse = []
        if self._at_kw("el"):
            orelse = [self._if_stmt_from_elif()]
        elif self._at_kw("els"):
            self._advance()
            self._expect("COLON", "expected ':'")
            orelse = self._suite()
        return A.If(test, body, orelse, line=tok.line, col=tok.col)

    def _if_stmt_from_elif(self):
        tok = self._advance()  # 'el', consumed like 'i' for the nested node
        test = self._expr()
        self._expect("COLON", "expected ':'")
        body = self._suite()
        orelse = []
        if self._at_kw("el"):
            orelse = [self._if_stmt_from_elif()]
        elif self._at_kw("els"):
            self._advance()
            self._expect("COLON", "expected ':'")
            orelse = self._suite()
        node = A.If(test, body, orelse, line=tok.line, col=tok.col)
        node.is_elif = True  # marks this as part of an elif-chain, not a nested `i`
        return node

    def _while_stmt(self):
        tok = self._advance()  # 'wh'
        test = self._expr()
        self._expect("COLON", "expected ':'")
        body = self._suite()
        return A.While(test, body, line=tok.line, col=tok.col)

    def _for_stmt(self):
        tok = self._advance()  # 'fr'
        targets = [self._expect("NAME").value]
        while self._at("COMMA"):
            self._advance()
            targets.append(self._expect("NAME").value)
        self._expect_kw("n", "expected 'n'")
        it = self._expr()
        self._expect("COLON", "expected ':'")
        body = self._suite()
        return A.For(targets, it, body, line=tok.line, col=tok.col)

    def _funcdef(self):
        tok = self._advance()  # 'fn'
        name = self._expect("NAME").value
        self._expect("LPAREN", "expected '('")
        params, defaults = [], []
        if not self._at("RPAREN"):
            self._param(params, defaults)
            while self._at("COMMA"):
                self._advance()
                self._param(params, defaults)
        self._expect("RPAREN", "expected ')'")
        self._expect("COLON", "expected ':'")
        body = self._suite()
        return A.FunctionDef(name, params, defaults, body, line=tok.line, col=tok.col)

    def _param(self, params, defaults):
        pname = self._expect("NAME").value
        params.append(pname)
        if self._at("OP") and self._cur().value == "=":
            self._advance()
            defaults.append((pname, self._expr()))

    def _classdef(self):
        tok = self._advance()  # 'cls'
        name = self._expect("NAME").value
        bases = []
        if self._at("LPAREN"):
            self._advance()
            if not self._at("RPAREN"):
                bases.append(self._expr())
                while self._at("COMMA"):
                    self._advance()
                    bases.append(self._expr())
            self._expect("RPAREN")
        self._expect("COLON", "expected ':'")
        body = self._suite()
        return A.ClassDef(name, bases, body, line=tok.line, col=tok.col)

    def _simple_stmt(self):
        stmt = self._small_stmt()
        self._end_simple_stmt()
        return stmt

    def _end_simple_stmt(self):
        if self._at("NEWLINE"):
            self._advance()
        elif self._at("ENDMARKER", "DEDENT"):
            pass
        else:
            self._error(f"unexpected {self._cur().value!r}")

    def _small_stmt(self):
        if self._at_kw("ret"):
            tok = self._advance()
            if self._at("NEWLINE", "ENDMARKER", "DEDENT"):
                return A.Return(None, line=tok.line, col=tok.col)
            return A.Return(self._testlist(), line=tok.line, col=tok.col)
        if self._at_kw("imp"):
            return self._import_stmt()
        if self._at_kw("frm"):
            return self._fromimport_stmt()
        return self._expr_stmt()

    def _import_stmt(self):
        tok = self._advance()  # 'imp'
        names = [self._dotted_name()]
        while self._at("COMMA"):
            self._advance()
            names.append(self._dotted_name())
        return A.Import(names, line=tok.line, col=tok.col)

    def _fromimport_stmt(self):
        tok = self._advance()  # 'frm'
        module = self._dotted_name()
        self._expect_kw("imp", "expected 'imp'")
        names = []
        if self._at("OP") and self._cur().value == "*":
            self._advance()
            names.append("*")
        else:
            names.append(self._expect("NAME").value)
            while self._at("COMMA"):
                self._advance()
                names.append(self._expect("NAME").value)
        return A.ImportFrom(module, names, line=tok.line, col=tok.col)

    def _dotted_name(self):
        parts = [self._expect("NAME").value]
        while self._at("DOT"):
            self._advance()
            parts.append(self._expect("NAME").value)
        return ".".join(parts)

    def _expr_stmt(self):
        tok = self._cur()
        first = self._testlist()
        if self._at("OP") and self._cur().value == "=":
            targets = [first]
            value = None
            while self._at("OP") and self._cur().value == "=":
                self._advance()
                value = self._testlist()
                targets.append(value)
            value = targets.pop()
            return A.Assign(targets, value, line=tok.line, col=tok.col)
        if self._at("OP") and self._cur().value in AUG_OPS:
            op = self._advance().value
            value = self._testlist()
            return A.AugAssign(first, op, value, line=tok.line, col=tok.col)
        return A.ExprStmt(first, line=tok.line, col=tok.col)

    def _testlist(self):
        tok = self._cur()
        first = self._expr()
        if self._at("COMMA"):
            elts = [first]
            while self._at("COMMA"):
                self._advance()
                if self._at("NEWLINE", "ENDMARKER", "RPAREN", "OP") and not self._starts_expr():
                    break
                elts.append(self._expr())
            return A.TupleLit(elts, line=tok.line, col=tok.col)
        return first

    def _starts_expr(self):
        return self._cur().type in (
            "NAME", "NUMBER", "STRING", "LPAREN", "LBRACKET", "LBRACE",
        ) or (self._at("OP") and self._cur().value in ("-", "+", "!"))

    # -- expressions (precedence climbing) --------------------------------
    def _expr(self):
        return self._or_test()

    def _or_test(self):
        tok = self._cur()
        left = self._and_test()
        if self._at("OP") and self._cur().value == "|":
            values = [left]
            while self._at("OP") and self._cur().value == "|":
                self._advance()
                values.append(self._and_test())
            return A.BoolOp("or", values, line=tok.line, col=tok.col)
        return left

    def _and_test(self):
        tok = self._cur()
        left = self._not_test()
        if self._at("OP") and self._cur().value == "&":
            values = [left]
            while self._at("OP") and self._cur().value == "&":
                self._advance()
                values.append(self._not_test())
            return A.BoolOp("and", values, line=tok.line, col=tok.col)
        return left

    def _not_test(self):
        if self._at("OP") and self._cur().value == "!":
            tok = self._advance()
            return A.UnaryOp("not", self._not_test(), line=tok.line, col=tok.col)
        return self._comparison()

    def _comparison(self):
        tok = self._cur()
        left = self._arith()
        ops, comparators = [], []
        while self._at("OP") and self._cur().value in COMPARE_OPS:
            ops.append(self._advance().value)
            comparators.append(self._arith())
        if ops:
            return A.Compare(left, ops, comparators, line=tok.line, col=tok.col)
        return left

    def _arith(self):
        tok = self._cur()
        left = self._term()
        while self._at("OP") and self._cur().value in ("+", "-"):
            op = self._advance().value
            right = self._term()
            left = A.BinOp(left, op, right, line=tok.line, col=tok.col)
        return left

    def _term(self):
        tok = self._cur()
        left = self._factor()
        while self._at("OP") and self._cur().value in ("*", "/", "//", "%"):
            op = self._advance().value
            right = self._factor()
            left = A.BinOp(left, op, right, line=tok.line, col=tok.col)
        return left

    def _factor(self):
        if self._at("OP") and self._cur().value in ("-", "+"):
            tok = self._advance()
            return A.UnaryOp(tok.value, self._factor(), line=tok.line, col=tok.col)
        return self._power()

    def _power(self):
        tok = self._cur()
        base = self._atom_trailer()
        if self._at("OP") and self._cur().value == "**":
            self._advance()
            exponent = self._factor()
            return A.BinOp(base, "**", exponent, line=tok.line, col=tok.col)
        return base

    def _atom_trailer(self):
        node = self._atom()
        while True:
            if self._at("DOT"):
                tok = self._advance()
                attr = self._expect("NAME").value
                node = A.Attribute(node, attr, line=tok.line, col=tok.col)
            elif self._at("LPAREN"):
                tok = self._advance()
                args, kwargs = self._arglist()
                self._expect("RPAREN", "expected ')'")
                node = A.Call(node, args, kwargs, line=tok.line, col=tok.col)
            elif self._at("LBRACKET"):
                tok = self._advance()
                index = self._expr()
                self._expect("RBRACKET", "expected ']'")
                node = A.Subscript(node, index, line=tok.line, col=tok.col)
            else:
                break
        return node

    def _arglist(self):
        args, kwargs = [], []
        if self._at("RPAREN"):
            return args, kwargs
        self._one_arg(args, kwargs)
        while self._at("COMMA"):
            self._advance()
            if self._at("RPAREN"):
                break
            self._one_arg(args, kwargs)
        return args, kwargs

    def _one_arg(self, args, kwargs):
        if self._at("NAME") and self._peek_type(1) == "OP" and self.tokens[self.pos + 1].value == "=":
            name = self._advance().value
            self._advance()  # '='
            kwargs.append((name, self._expr()))
        else:
            args.append(self._expr())

    def _atom(self):
        tok = self._cur()
        if tok.type == "NUMBER":
            self._advance()
            return A.Num(tok.value, line=tok.line, col=tok.col)
        if tok.type == "STRING":
            self._advance()
            return A.Str(tok.value, line=tok.line, col=tok.col)
        if tok.type == "NAME":
            self._advance()
            return A.Name(tok.value, line=tok.line, col=tok.col)
        if tok.type == "LPAREN":
            self._advance()
            if self._at("RPAREN"):
                self._advance()
                return A.TupleLit([], line=tok.line, col=tok.col)
            first = self._expr()
            if self._at("COMMA"):
                elts = [first]
                while self._at("COMMA"):
                    self._advance()
                    if self._at("RPAREN"):
                        break
                    elts.append(self._expr())
                self._expect("RPAREN", "expected ')'")
                return A.TupleLit(elts, line=tok.line, col=tok.col)
            self._expect("RPAREN", "expected ')'")
            return first
        if tok.type == "LBRACKET":
            self._advance()
            elts = []
            if not self._at("RBRACKET"):
                elts.append(self._expr())
                while self._at("COMMA"):
                    self._advance()
                    if self._at("RBRACKET"):
                        break
                    elts.append(self._expr())
            self._expect("RBRACKET", "expected ']'")
            return A.ListLit(elts, line=tok.line, col=tok.col)
        if tok.type == "LBRACE":
            self._advance()
            keys, values = [], []
            if not self._at("RBRACE"):
                k = self._expr()
                self._expect("COLON", "expected ':'")
                v = self._expr()
                keys.append(k)
                values.append(v)
                while self._at("COMMA"):
                    self._advance()
                    if self._at("RBRACE"):
                        break
                    k = self._expr()
                    self._expect("COLON", "expected ':'")
                    v = self._expr()
                    keys.append(k)
                    values.append(v)
            self._expect("RBRACE", "expected '}'")
            return A.DictLit(keys, values, line=tok.line, col=tok.col)
        self._error(f"unexpected token {tok.value!r}")


def parse(tokens, filename="<string>"):
    return Parser(tokens, filename).parse_module()
