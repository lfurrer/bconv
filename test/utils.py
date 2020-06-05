"""
Testing utilities.
"""


__author__ = "Lenz Furrer"


import io
from pathlib import Path


DATA = Path(__file__).parent / 'data'


def get_cases(fmts):
    return [(fmt, path) for fmt in fmts for path in Path(DATA, fmt).glob('*')]


def path_id(value):
    if isinstance(value, Path):
        return value.stem


def xopen(source, fmt):
    """Text or binary IO, depending on the format."""
    binary = fmt.endswith(('xml', '.zip', '.tgz'))
    if isinstance(source, Path):
        if binary:
            f = open(source, mode='rb')
        else:
            f = open(source, encoding='utf8')
    else:
        if binary:
            f = io.BytesIO(source)
        else:
            f = io.StringIO(source)
    return f
