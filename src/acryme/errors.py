"""Acryme error types.

Every Acryme-level error carries file/line/column so the CLI can print
short, precise diagnostics instead of a raw Python traceback.
"""


class AcrymeError(Exception):
    def __init__(self, filename, line, col, message, error_type="Error"):
        self.filename = filename
        self.line = line
        self.col = col
        self.message = message
        self.error_type = error_type
        super().__init__(f"{filename}:{line}:{col} {error_type}: {message}")

    def render(self, source_lines):
        """Return a multi-line string with a caret pointing at the column."""
        header = f"{self.filename}:{self.line}:{self.col} {self.error_type}: {self.message}"
        idx = self.line - 1
        if 0 <= idx < len(source_lines):
            src_line = source_lines[idx].rstrip("\n")
            caret_pos = max(self.col - 1, 0)
            pointer = " " * caret_pos + "^"
            gutter = f"{self.line} | "
            return f"{header}\n{gutter}{src_line}\n{' ' * len(gutter)}{pointer}"
        return header


class AcrymeSyntaxError(AcrymeError):
    def __init__(self, filename, line, col, message):
        super().__init__(filename, line, col, message, "SyntaxError")
