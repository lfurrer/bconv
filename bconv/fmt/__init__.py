"""
Format converters.
"""


__author__ = "Lenz Furrer"


import io
from pathlib import Path

from . import txt
from . import csv_
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
    'txt.json': txt.TXTJSONLoader,
    'bioc_xml': bioc.BioCXMLLoader,
    'bioc_json': bioc.BioCJSONLoader,
    'conll': conll.CoNLLLoader,
    'pubtator': pubtator.PubTatorLoader,
    'pubtator_fbk': pubtator.PubTatorFBKLoader,
    'pxml': pubmed.PXMLLoader,
    'nxml': pubmed.PMCLoader,
}

FETCHERS = {
    'pubmed': pubmed.PXMLFetcher,
    'pmc': pubmed.PMCFetcher,
}

EXPORTERS = {
    'txt': txt.TXTFormatter,
    'txt.json': txt.TXTJSONFormatter,
    'csv': csv_.CSVFormatter,
    'tsv': csv_.TSVFormatter,
    'text_csv': csv_.TextCSVFormatter,
    'text_tsv': csv_.TextTSVFormatter,
    'bioc_xml': bioc.BioCXMLFormatter,
    'bioc_json': bioc.BioCJSONFormatter,
    'bionlp': brat.BioNLPFormatter,
    'brat': brat.BratFormatter,
    'conll': conll.CoNLLFormatter,
    'pubanno_json': pubanno.PubAnnoJSONFormatter,
    'pubanno_json.tgz': pubanno.PubAnnoTGZFormatter,
    'pubtator': pubtator.PubTatorFormatter,
    'pubtator_fbk': pubtator.PubTatorFBKFormatter,
    'europepmc': europepmc.EuPMCFormatter,
    'europepmc.zip': europepmc.EuPMCZipFormatter,
}


def load(source, fmt=None, mode='native', id_=None, **options):
    """
    Load a document or collection from a file.

    The mode parameter determines the return type:
        - native: a Document or Collection object, depending
            on the format;
        - collection: a Collection object wrapping all content;
        - lazy: an iterator of Document objects, consumed
            lazily if possible.
    """
    if fmt is None:
        fmt = _guess_format(source, LOADERS)
    loader = LOADERS[fmt](**options)
    return _load(loader, mode, source, id_)


def _load(loader, mode, source, id_):
    if mode == 'lazy' and hasattr(loader, 'iter_documents'):
        content = loader.iter_documents(source)
    else:
        content = loader.load_one(source, id_)

    if hasattr(loader, 'document'):
        if mode == 'lazy':
            content = iter([content])
        elif mode == 'collection':
            content = wrap_in_collection(content)

    return content


def loads(source, fmt, mode='native', id_=None, **options):
    """
    Load a document or collection from str or bytes.
    """
    wrap = io.StringIO if isinstance(source, str) else io.BytesIO
    return load(wrap(source), fmt, mode, id_, **options)


def fetch(query, fmt, mode='native', id_=None, **options):
    """
    Load a document or collection from a remote service.
    """
    fetcher = FETCHERS[fmt](**options)
    return _load(fetcher, mode, query, id_)


def dump(content, dest, fmt=None, **options):
    """
    Serialise a document or collection to a file.

    The destination can be a file open for writing or a
    path to a file or to an existing directory.
    """
    if fmt is None:
        fmt = _guess_format(dest, EXPORTERS)
    exporter = EXPORTERS[fmt](**options)
    if hasattr(dest, 'write'):
        exporter.write(content, dest)
    else:
        exporter.export(content, dest)


def dumps(content, fmt, **options):
    """
    Serialise a document or collection to str or bytes.
    """
    exporter = EXPORTERS[fmt](**options)
    return exporter.dumps(content)


def _guess_format(path, choices):
    try:
        path = Path(path)
    except TypeError:
        pass  # raise later
    else:
        suffix = path.suffix.lstrip('.').lower()
        if suffix in choices:
            return suffix
        # Try double suffices, eg. foo.bioc.json.
        suffix2 = path.with_suffix('').suffix.lstrip('.').lower()
        for joiner in ('_', '.'):
            fmt = joiner.join((suffix, suffix2))
            if fmt in choices:
                return fmt
    raise ValueError('cannot infer `fmt` from {}'.format(path))
