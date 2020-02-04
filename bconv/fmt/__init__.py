#!/usr/bin/env python3
# coding: utf8

# Author: Lenz Furrer, 2017--2020


"""
Format converters.
"""


# pylint: disable=wildcard-import

import io

from .txt import *
from .tsv import *
from .bioc import *
from .brat import *
from .conll import *
from .pubmed import *
from .pubanno import *
from .pubtator import *
from .europepmc import *
from .bioc import wrap_in_collection


# Keep these mappings up to date.
LOADERS = {
    'txt': TXTLoader,
    'txt_json': TXTJSONLoader,
    'bioc_xml': BioCXMLLoader,
    'bioc_json': BioCJSONLoader,
    'conll': CoNLLLoader,
    'pubtator': PubTatorLoader,
    'pubtator_fbk': PubTatorFBKLoader,
    'pubmed': PXMLFetcher,
    'pxml': PXMLLoader,
    'pxml.gz': MedlineLoader,
    'pmc': PMCFetcher,
    'nxml': PMCLoader,
}

INFMTS = list(LOADERS.keys())

EXPORTERS = {
    'tsv': TSVFormatter,
    'txt': TXTFormatter,
    'text_tsv': TextTSVFormatter,
    'bioc_xml': BioCXMLFormatter,
    'bioc_json': BioCJSONFormatter,
    'bionlp': BioNLPFormatter,
    'brat': BratFormatter,
    'conll': CoNLLFormatter,
    'pubanno_json': PubAnnoJSONFormatter,
    'pubtator': PubTatorFormatter,
    'pubtator_fbk': PubTatorFBKFormatter,
    'europepmc': EuPMCFormatter,
    'europepmc.zip': EuPMCZipFormatter,
}

OUTFMTS = list(EXPORTERS.keys())


def load(fmt, source, id_=None, mode='auto', **options):
    """
    Load a document or collection from a file.

    The mode parameter determines the return type:
        - collection: always one Collection object
        - document: always an iterator of Document objects
        - auto: always one object of the native type
                (Document or Collection)
    """
    loader = LOADERS[fmt](**options)
    if mode == 'document' and hasattr(loader, 'iter_documents'):
        content = loader.iter_documents(source, id_)
    else:
        content = loader.load_one(source, id_)

    if hasattr(loader, 'document'):
        if mode == 'document':
            content = iter([content])
        elif mode == 'collection':
            content = wrap_in_collection(content)

    return content


def loads(fmt, source, id_=None, mode='auto', **options):
    """
    Load a document or collection from str or bytes.
    """
    wrap = io.StringIO if isinstance(source, str) else io.BytesIO
    return load(fmt, wrap(source), id_, mode, **options)


def dump(fmt, content, stream=None, dest='.', **options):
    """
    Serialise a document or collection to a file.
    """
    exporter = EXPORTERS[fmt](**options)
    if stream is None:
        exporter.export(content, dest)
    else:
        exporter.write(content, stream)


def dumps(fmt, content, **options):
    """
    Serialise a document or collection to str or bytes.
    """
    exporter = EXPORTERS[fmt](**options)
    return exporter.dumps(content)
