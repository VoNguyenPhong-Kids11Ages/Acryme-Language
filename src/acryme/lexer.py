"""Acryme lexer.

Turns .ac source text into a flat token stream, handling Python-style
significant indentation (INDENT/DEDENT), implicit line joining inside
brackets, comments, strings (incl. f-strings), numbers and operators.
"""

from .errors import AcrymeSyntaxError

# Grammar keywords. These are *soft* keywords: the lexer emits them as
# plain NAME tokens (like any identifier), and the parser only treats
# one as a keyword when it appears in a position where a keyword is
# grammatically expected (start of a statement, the 'n' of a `fr` loop,
# etc). This matters because the spec's own examples reuse `i` and `n`
# as ordinary loop-variable names (see `fr i n range(3): ...`).
KEYWORDS = {"i", "el", "els", "wh", "fr", "n", "fn", "ret", "cls", "imp", "frm"}

# Plain identifiers that are only renamed at code-generation time.
# (T/F/N/pnt behave like normal names to the parser.)
RENAME_NAMES = {"T": "True", "F": "False", "N": "None", "pnt": "print"}

MULTI_OPS = ["**=", "//=", "**", "//", "==", "!=", ">=", "<=",
             "+=", "-=", "*=", "/=", "%="]
SINGLE_OP_TYPES = {
    "(": "LPAREN", ")": "RPAREN",
    "[": "LBRACKET", "]": "RBRACKET",
    "{": "LBRACE", "}": "RBRACE",
    ":": "COLON", ",": "COMMA", ".": "DOT",
}
SINGLE_OPS = "+-*/%<>=&|!.,:()[]{}"
STRING_PREFIXES = {"f", "r", "fr", "rf", "b", "rb"}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class Lexer:
    def __init__(self, source, filename="<string>"):
        # Normalize so a trailing newline always exists; simplifies EOF handling.
        self.src = source if source.endswith("\n") else source + "\n"
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.paren_depth = 0
        self.indent_stack = [0]
        self.tokens = []
        self.at_line_start = True

    # -- low level helpers -------------------------------------------------
    def _error(self, msg, line=None, col=None):
        raise AcrymeSyntaxError(self.filename, line or self.line, col or self.col, msg)

    def _peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else ""

    def _advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    # -- main entry ----------------------------------------------------
    def tokenize(self):
        while self.pos < len(self.src):
            if self.at_line_start and self.paren_depth == 0:
                consumed_blank = self._handle_indentation()
                if consumed_blank:
                    continue
                self.at_line_start = False
                continue

            ch = self._peek()
            if ch == "":
                break
            if ch == "#":
                while self._peek() not in ("", "\n"):
                    self._advance()
                continue
            if ch == "\n":
                nl_line, nl_col = self.line, self.col
                self._advance()
                if self.paren_depth == 0:
                    self._emit_newline(nl_line, nl_col)
                    self.at_line_start = True
                continue
            if ch in " \t":
                self._advance()
                continue
            if ch == "\\" and self._peek(1) == "\n":
                self._advance()
                self._advance()
                continue
            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                self._read_number()
                continue
            if ch.isalpha() or ch == "_":
                self._read_name_or_string()
                continue
            if ch in ("'", '"'):
                self._read_string(prefix="")
                continue
            self._read_operator()

        if self.tokens and self.tokens[-1].type != "NEWLINE":
            self._emit_newline()
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token("DEDENT", "", self.line, 1))
        self.tokens.append(Token("ENDMARKER", "", self.line, 1))
        return self.tokens

    # -- indentation -----------------------------------------------------
    def _handle_indentation(self):
        """Consume leading whitespace of a new logical line.

        Returns True if the line was blank/comment-only (and thus fully
        consumed here, with no tokens produced), False if real code
        follows and INDENT/DEDENT bookkeeping is done.
        """
        indent = 0
        while self._peek() == " ":
            indent += 1
            self._advance()
        if self._peek() == "\t":
            self._error("tabs are not allowed for indentation; use spaces")
        nxt = self._peek()
        if nxt == "#":
            while self._peek() not in ("", "\n"):
                self._advance()
            nxt = self._peek()
        if nxt in ("\n", ""):
            if nxt == "\n":
                self._advance()
            return True

        current = self.indent_stack[-1]
        if indent > current:
            self.indent_stack.append(indent)
            self.tokens.append(Token("INDENT", "", self.line, 1))
        elif indent < current:
            while indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.tokens.append(Token("DEDENT", "", self.line, 1))
            if indent != self.indent_stack[-1]:
                self._error("inconsistent indentation", self.line, indent + 1)
        return False

    def _emit_newline(self, line=None, col=None):
        if self.tokens and self.tokens[-1].type not in ("NEWLINE", "INDENT", "DEDENT"):
            self.tokens.append(Token("NEWLINE", "\n", line or self.line, col or self.col))

    # -- literals ----------------------------------------------------------
    def _read_number(self):
        start_col = self.col
        num = ""
        while self._peek().isdigit():
            num += self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            num += self._advance()
            while self._peek().isdigit():
                num += self._advance()
        if self._peek() in ("e", "E") and (self._peek(1).isdigit() or
                                            (self._peek(1) in "+-" and self._peek(2).isdigit())):
            num += self._advance()
            if self._peek() in "+-":
                num += self._advance()
            while self._peek().isdigit():
                num += self._advance()
        self.tokens.append(Token("NUMBER", num, self.line, start_col))

    def _read_name_or_string(self):
        start_col = self.col
        name = ""
        while self._peek().isalnum() or self._peek() == "_":
            name += self._advance()
        if name.lower() in STRING_PREFIXES and self._peek() in ("'", '"'):
            self._read_string(prefix=name, start_col=start_col)
            return
        # All identifiers -- including soft keywords -- are NAME tokens;
        # the parser decides from context whether one acts as a keyword.
        self.tokens.append(Token("NAME", name, self.line, start_col))

    def _read_string(self, prefix, start_col=None):
        start_line = self.line
        start_col = start_col if start_col is not None else self.col
        quote = self._advance()
        triple = False
        if self._peek() == quote and self._peek(1) == quote:
            triple = True
            self._advance()
            self._advance()
        buf = prefix + quote * (3 if triple else 1)
        while True:
            ch = self._peek()
            if ch == "":
                self._error("unterminated string literal", start_line, start_col)
            if ch == "\\":
                buf += self._advance()
                if self._peek() != "":
                    buf += self._advance()
                continue
            if not triple and ch == "\n":
                self._error("unterminated string literal", start_line, start_col)
            if ch == quote:
                if triple:
                    if self._peek(1) == quote and self._peek(2) == quote:
                        buf += self._advance() + self._advance() + self._advance()
                        break
                    buf += self._advance()
                    continue
                buf += self._advance()
                break
            buf += self._advance()
        self.tokens.append(Token("STRING", buf, start_line, start_col))

    def _read_operator(self):
        start_col = self.col
        for op in MULTI_OPS:
            if self.src.startswith(op, self.pos):
                for _ in op:
                    self._advance()
                self.tokens.append(Token("OP", op, self.line, start_col))
                return
        ch = self._peek()
        if ch in "([{":
            self.paren_depth += 1
        elif ch in ")]}":
            self.paren_depth = max(0, self.paren_depth - 1)
        if ch in SINGLE_OPS:
            self._advance()
            ttype = SINGLE_OP_TYPES.get(ch, "OP")
            self.tokens.append(Token(ttype, ch, self.line, start_col))
            return
        self._error(f"unexpected character {ch!r}", self.line, start_col)


def tokenize(source, filename="<string>"):
    return Lexer(source, filename).tokenize()
