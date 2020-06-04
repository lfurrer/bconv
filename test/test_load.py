"""
Test bconv.load() and bconv.fetch().
"""


__author__ = "Lenz Furrer"


import json
import urllib.request
from pathlib import Path

import pytest

import bconv

from .utils import DATA, get_cases, path_id, xopen


TEXT_ONLY = 'text-only'
STRIP_WS = 'strip-ws'
SKIP_CUI = 'skip-cui'
STR_IDS = 'str-ids'

RESTRICTIONS = {
    'conll': {STRIP_WS, SKIP_CUI},
    'pubtator_fbk': {SKIP_CUI},
    'bioc_json': {STR_IDS},
    'bioc_xml': {STR_IDS},
    'txt': {TEXT_ONLY, STRIP_WS},
    'txt.json': {TEXT_ONLY, STRIP_WS},
    'pxml': {TEXT_ONLY},
    'nxml': {TEXT_ONLY},
    'pubmed': {TEXT_ONLY},
    'pmc': {TEXT_ONLY},
}


@pytest.fixture(scope="module")
def expected():
    """Read the expected outputs from JSON dumps."""
    exp = {}
    for p in Path(DATA, 'internal').glob('*.json'):
        with open(p, 'r', encoding='utf8') as f:
            exp[p.stem] = json.load(f)
    return exp


@pytest.mark.parametrize('fmt,path', get_cases(bconv.LOADERS), ids=path_id)
def test_load(fmt, path, expected):
    """Test the load function."""
    parsed = bconv.load(path, fmt)
    _validate(parsed, fmt, expected[path.stem])


@pytest.mark.parametrize('fmt,path', get_cases(bconv.LOADERS), ids=path_id)
def test_loads(fmt, path, expected):
    """Test the loads function."""
    with xopen(path, fmt) as f:
        parsed = bconv.loads(f.read(), fmt)
    _validate(parsed, fmt, expected[path.stem])


@pytest.mark.parametrize('fmt,path', get_cases(bconv.FETCHERS), ids=path_id)
def test_fetch(fmt, path, expected, monkeypatch):
    """Test the fetch function."""
    def _mock_response(_):
        return open(path, 'rb')
    monkeypatch.setattr(urllib.request, 'urlopen', _mock_response)
    parsed = bconv.fetch('ignored', fmt)
    _validate(parsed, fmt, expected[path.stem])


def _validate(parsed, fmt, exp):
    restrictions = RESTRICTIONS.get(fmt, ())
    text = _get_text(parsed)
    ref = exp['text']
    if STRIP_WS in restrictions:
        text = _nested_sentences(text, str.strip)
        ref = _nested_sentences(ref, str.strip)
    assert text == ref

    if TEXT_ONLY not in restrictions:
        ref = exp['entities']
        if SKIP_CUI in restrictions:
            ref = [list(_skip_cui(doc)) for doc in ref]
        if STR_IDS in restrictions:
            ref = [list(_str_ids(doc)) for doc in ref]
        assert _get_entities(parsed) == ref


def _get_text(content):
    return _nested_sentences(content.units('document'), lambda sent: sent.text)


def _nested_sentences(docs, call):
    return [[[call(sent) for sent in sec] for sec in doc] for doc in docs]


def _get_entities(content):
    return [[[getattr(entity, att) for att in entity.__slots__]
             for entity in doc.iter_entities()]
            for doc in content.units('document')]


def _skip_cui(entities):
    for *entity, info in entities:
        info = {k: v for k, v in info.items() if k != 'cui'}
        yield [*entity, info]


def _str_ids(entities):
    for id_, *entity in entities:
        yield [str(id_), *entity]
