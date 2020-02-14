#!/usr/bin/env python3
# coding: utf8

# Author: Lenz Furrer, 2017--2020


"""
Format converters.
"""


import io

from . import txt
from . import tsv
from . import bioc
from . import brat
from . import conll
from . import pubmed
from . import pubanno
from . import pubtator
from . import europepmc
from ._load import wrap_in_collection


# Keep these mappings up to date.
LOADERS = {
    'txt': txt.TXTLoader,
    'txt_json': txt.TXTJSONLoader,
    'bioc_xml': bioc.BioCXMLLoader,
    'bioc_json': bioc.BioCJSONLoader,
    'conll': conll.CoNLLLoader,
    'pubtator': pubtator.PubTatorLoader,
    'pubtator_fbk': pubtator.PubTatorFBKLoader,
    'pxml': pubmed.PXMLLoader,
    'pxml.gz': pubmed.MedlineLoader,
    'nxml': pubmed.PMCLoader,
}

FETCHERS = {
    'pubmed': pubmed.PXMLFetcher,
    'pmc': pubmed.PMCFetcher,
}

EXPORTERS = {
    'txt': txt.TXTFormatter,
    'tsv': tsv.TSVFormatter,
    'text_tsv': tsv.TextTSVFormatter,
    'bioc_xml': bioc.BioCXMLFormatter,
    'bioc_json': bioc.BioCJSONFormatter,
    'bionlp': brat.BioNLPFormatter,
    'brat': brat.BratFormatter,
    'conll': conll.CoNLLFormatter,
    'pubanno_json': pubanno.PubAnnoJSONFormatter,
    'pubtator': pubtator.PubTatorFormatter,
    'pubtator_fbk': pubtator.PubTatorFBKFormatter,
    'europepmc': europepmc.EuPMCFormatter,
    'europepmc.zip': europepmc.EuPMCZipFormatter,
}


def load(fmt, source, id_=None, mode='auto', **options):
    """
    Load a document or collection from a file.

    The mode parameter determines the return type:
        - collection: a Collection object
        - document: an iterator of Document objects
        - auto: an object of the format's native type
                (Document or Collection)
    """
    loader = LOADERS[fmt](**options)
    return _load(loader, source, id_, mode)

def _load(loader, source, id_, mode):
    if mode == 'document' and hasattr(loader, 'iter_documents'):
        content = loader.iter_documents(source)
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


def fetch(fmt, query, id_=None, mode='auto', **options):
    """
    Load a document or collection from a remote service.
    """
    fetcher = FETCHERS[fmt](**options)
    return _load(fetcher, query, id_, mode)


def dump(fmt, content, stream=None, dest=None, **options):
    """
    Serialise a document or collection to a file.
    """
    exporter = EXPORTERS[fmt](**options)
    if stream is dest is None:
        raise ValueError(
            'missing argument: one of stream or dest must be given')
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
