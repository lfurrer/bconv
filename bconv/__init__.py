"""
bconv: converter for bio-NLP formats.
"""


__author__ = "Lenz Furrer"

__version__ = '1.2.0'


from .fmt import load, loads, fetch, dump, dumps, LOADERS, FETCHERS, EXPORTERS
from .doc.document import Collection, Document, Entity, Relation
