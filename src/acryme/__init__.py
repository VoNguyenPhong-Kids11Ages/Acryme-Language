"""Acryme: write less, do more. A minimal Python-transpiled language."""

__version__ = "0.1.0"

from .lexer import tokenize
from .parser import parse
from .codegen import to_python

__all__ = ["tokenize", "parse", "to_python", "__version__"]
