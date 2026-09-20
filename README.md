# Acryme

*Write less. Do more.*

Acryme (v0.1.0) is a minimal, Python-compatible language: same grammar
as Python, with every keyword and a few operators shortened. Programs
transpile to Python ("Pyhn") and run on the Python runtime.

```
diem = 8
i diem >= 8:
  pnt("Giỏi")
el diem >= 5:
  pnt("Khá")
els:
  pnt("Trung bình")
```

## Install / run

```
pip install acryme
```

That puts an `a` command on your PATH — no `python3` prefix needed:

```
a                         # interactive REPL — just start typing Acryme
a examples/grade.ac       # run a file directly, no subcommand needed
a rn main.ac              # same as above, spelled out
a bd main.ac              # build: transpile to main.py
a cp main.ac              # compile (alias of bd for v0.1)
a db main.ac              # debug: print tokens, AST, generated Pyhn, then run
a fmt main.ac             # format a file in place (2-space indent)
a v                       # version
a h                       # help
```

Running `a` with no arguments starts a REPL: type a line and it runs
immediately (variables persist across lines); end a line with `:` to
start a block, keep typing it indented yourself, and a blank line
runs the whole block. `exit` or Ctrl-D quits.

### Without installing

Not on PyPI yet, or just trying it locally? Clone/download this repo
and run it straight from source with plain Python 3, no install step:

```
python3 -m acryme.cli rn examples/grade.ac
```

or install it from the local checkout with `pip install .` (or
`pip install -e .` for an editable install while developing) to get
the same `a` command as above.

## Keyword table

| Acryme | Pyhn/Python | | Acryme | Pyhn/Python |
|---|---|---|---|---|
| `i`   | `if`     | | `fn`  | `def`    |
| `el`  | `elif`   | | `ret` | `return` |
| `els` | `else`   | | `cls` | `class`  |
| `wh`  | `while`  | | `imp` | `import` |
| `fr`  | `for`    | | `frm` | `from`   |
| `n`   | `in`     | | `pnt()` | `print()` |
| `T` / `F` / `N` | `True` / `False` / `None` | | `&` `|` `!` | `and` `or` `not` |

`i`, `n`, `fn`, etc. are *soft* keywords — they only act as keywords at
the start of a statement (or right after a `fr ... n ...`), so they
can still be used as ordinary variable names elsewhere, exactly as in
the spec's own `fr i n range(3):` example.

Everything else (operators, numbers, strings, f-strings, lists,
dicts, tuples, comments, indentation-based blocks) is plain Python
syntax, unchanged.

## What's implemented (P0, done)

`.ac` files, `a rn`, variables (`=`, `+=` etc.), `pnt`, `i/el/els`,
`wh`, `fr/n`, `fn/ret`, arithmetic and comparisons, `&`/`|`/`!`,
strings/f-strings, lists/dicts/tuples, classes with inheritance,
`imp`/`frm ... imp`, 2-space indentation, `main.ac:line:col` error
reporting with a source-line caret (no raw Python tracebacks for
syntax errors), and Acryme → Pyhn transpilation.

## What's implemented (P1, partial)

`cls`, `imp`/`frm` ✅. `a fmt` works but does not yet preserve
comments or original parenthesization. `a bd`/`a cp` write a `.py`
file next to the source.

## Not implemented (P2, by design)

Acryme-native `try/except` keywords (`tr`/`ex`/`fin`/`ras` — Acryme
currently accepts plain Python `try:`/`except:` if you write it),
the bytecode VM, an optimizer, and a package manager. Per the spec:
don't build the spaceship before the wheel turns.

## Architecture

```
main.ac -> Lexer -> Parser -> AST -> Acryme->Pyhn codegen -> exec()
```

- `src/acryme/lexer.py` — tokenizer (INDENT/DEDENT, strings incl.
  f-strings, comments, soft keywords).
- `src/acryme/parser.py` — recursive-descent parser producing an AST.
- `src/acryme/ast_nodes.py` — AST node types.
- `src/acryme/codegen.py` — AST → Python source.
- `src/acryme/formatter.py` — AST → canonical Acryme source (for `a fmt`).
- `src/acryme/errors.py` — `file:line:col` error type with a caret render.
- `src/acryme/cli.py` — the `a` subcommands and REPL; `a = acryme.cli:main`
  is registered as the installed console script in `pyproject.toml`.

## Examples

See `examples/hello.ac` and `examples/grade.ac` (the spec's own test
case — running it prints `Khá / Khá / Giỏi`, matching section 23).

## Publishing to PyPI (for maintainers)

```
python3 -m pip install --upgrade build twine
python3 -m build                 # makes dist/acryme-0.1.0.tar.gz + .whl
python3 -m twine upload dist/*   # asks for your PyPI API token
```

You'll need a free account at https://pypi.org, and an API token from
https://pypi.org/manage/account/#api-tokens (use it as the username
`__token__` when twine asks). It's worth doing a `python3 -m twine
upload --repository testpypi dist/*` against https://test.pypi.org
first to check everything installs cleanly before publishing for
real — package names on PyPI are first-come-first-served and can't be
reused once taken, even if you delete the release.
