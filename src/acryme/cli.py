"""The `a` command-line tool: rn, bd, cp, db, fmt, v, h."""

import sys
import os

from .lexer import tokenize
from .parser import parse
from .codegen import to_python
from .formatter import to_acryme
from .errors import AcrymeError
from . import __version__

HELP = """Acryme %s -- write less. do more.

Usage:
  a                 start an interactive REPL (write Acryme, get Pyhn)
  a <file.ac>        run a program (shorthand for `a rn <file.ac>`)
  a rn <file.ac>    run a program
  a bd <file.ac>    build: transpile to a .py file
  a cp <file.ac>    compile (alias of bd for v0.1)
  a db <file.ac>    debug: show tokens, AST and generated Pyhn, then run
  a fmt <file.ac>   format a file in place (2-space indent)
  a v               print version
  a h               show this help

REPL: type one line to run it immediately; end a line with ':' to
start a block, then keep typing (indent it yourself) and finish with
a blank line to run the whole block. 'h'/'v' show help/version,
'exit' or Ctrl-D quits.
""" % __version__


def _read_source(path):
    if not os.path.isfile(path):
        print(f"a: no such file: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _compile_to_ast(source, filename):
    tokens = tokenize(source, filename)
    return parse(tokens, filename)


def _report_error(err: AcrymeError, source):
    lines = source.splitlines(keepends=True)
    print(err.render(lines), file=sys.stderr)
    sys.exit(1)


def cmd_rn(path):
    source = _read_source(path)
    try:
        module = _compile_to_ast(source, path)
        py_src = to_python(module)
    except AcrymeError as e:
        _report_error(e, source)
        return
    code = compile(py_src, filename=path, mode="exec")
    g = {"__name__": "__main__", "__file__": path}
    try:
        exec(code, g)
    except SystemExit:
        raise
    except Exception as e:
        print(f"{path}: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def _build(path):
    source = _read_source(path)
    try:
        module = _compile_to_ast(source, path)
        py_src = to_python(module)
    except AcrymeError as e:
        _report_error(e, source)
        return None
    out_path = os.path.splitext(path)[0] + ".py"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(py_src)
    return out_path


def cmd_bd(path):
    out_path = _build(path)
    if out_path:
        print(f"Built -> {out_path}")


def cmd_cp(path):
    out_path = _build(path)
    if out_path:
        print(f"Compiled -> {out_path}")


def cmd_db(path):
    source = _read_source(path)
    try:
        tokens = tokenize(source, path)
        print("-- tokens --")
        for t in tokens:
            print(" ", t)
        module = parse(tokens, path)
        print("-- ast --")
        print(" ", module)
        py_src = to_python(module)
        print("-- pyhn --")
        print(py_src)
    except AcrymeError as e:
        _report_error(e, source)
        return
    print("-- run --")
    code = compile(py_src, filename=path, mode="exec")
    g = {"__name__": "__main__", "__file__": path}
    try:
        exec(code, g)
    except Exception as e:
        print(f"{path}: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_fmt(path):
    source = _read_source(path)
    try:
        module = _compile_to_ast(source, path)
        formatted = to_acryme(module)
    except AcrymeError as e:
        _report_error(e, source)
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(formatted)
    print(f"Formatted {path}")


def cmd_v():
    print(f"Acryme {__version__}")
    print("Pyhn backend")


def cmd_h():
    print(HELP)


def _repl_run(lines, g):
    source = "\n".join(lines) + "\n"
    try:
        module = _compile_to_ast(source, "<repl>")
        py_src = to_python(module)
    except AcrymeError as e:
        print(e.render(source.splitlines(keepends=True)))
        return
    try:
        code = compile(py_src, filename="<repl>", mode="exec")
        exec(code, g)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")


def cmd_repl():
    print(f"Acryme {__version__} -- Pyhn backend. 'h' for help, 'exit' or Ctrl-D to quit.")
    g = {"__name__": "__main__"}
    buf = []
    continuation = False
    while True:
        prompt = "... " if continuation else "ac> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print()
            buf, continuation = [], False
            continue
        stripped = line.strip()
        if not continuation:
            if stripped in ("exit", "exit()", "quit", "quit()"):
                return
            if stripped == "h":
                cmd_h()
                continue
            if stripped == "v":
                cmd_v()
                continue
            if stripped == "":
                continue
            buf = [line]
            if stripped.endswith(":"):
                continuation = True
            else:
                _repl_run(buf, g)
                buf = []
        else:
            if stripped == "":
                _repl_run(buf, g)
                buf, continuation = [], False
            else:
                buf.append(line)


COMMANDS = {
    "rn": cmd_rn, "bd": cmd_bd, "cp": cmd_cp,
    "db": cmd_db, "fmt": cmd_fmt,
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        cmd_repl()
        return
    if argv[0] in ("h", "-h", "--help"):
        cmd_h()
        return
    if argv[0] in ("v", "-v", "--version"):
        cmd_v()
        return
    cmd = argv[0]
    if cmd in COMMANDS:
        if len(argv) < 2:
            print(f"a: '{cmd}' requires a file argument, e.g. a {cmd} main.ac", file=sys.stderr)
            sys.exit(1)
        COMMANDS[cmd](argv[1])
        return
    # Not a known subcommand: treat the bare argument as `a rn <file>`,
    # so `a main.ac` works without spelling out `rn`.
    cmd_rn(cmd)


if __name__ == "__main__":
    main()
