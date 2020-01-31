#!/usr/bin/env python3
# coding: utf8

# Author: Lenz Furrer, 2017--2020


"""
Format converters.
"""


from .txt import *
from .pubmed import *
from .tsv import *
from .bioc import *
from .brat import *
from .conll import *
from .pubanno import *
from .pubtator import *
from .europepmc import *


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
