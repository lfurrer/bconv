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
NO_RELS = 'no-rels'
BIN_REL_ONLY = 'bin-rel-only'
STRIP_WS = 'strip-ws'
SKIP_CUI = 'skip-cui'
STR_IDS = 'str-ids'
UNNEST = 'unnest'

RESTRICTIONS = {
    # Format-specific relaxations.
    'conll': {STRIP_WS, NO_RELS, SKIP_CUI},
    'pubanno_json': {BIN_REL_ONLY},
    'pubanno_json.tgz': {BIN_REL_ONLY},
    'pubtator': {NO_RELS},
    'pubtator_fbk': {NO_RELS, SKIP_CUI},
    'bioc_json': {STR_IDS},
    'bioc_xml': {STR_IDS},
    'txt': {TEXT_ONLY, STRIP_WS},
    'txt.json': {TEXT_ONLY, STRIP_WS},
    'pxml': {TEXT_ONLY},
    'nxml': {TEXT_ONLY},
    'pubmed': {TEXT_ONLY},
    'pmc': {TEXT_ONLY},

    # Document-specific relaxations.

    # Format- and document-specific relaxations.
    ('txt', 'CRAFT-example'): {UNNEST},
    ('conll', 'elliptic-coordination'): {TEXT_ONLY},
    ('pubtator', 'elliptic-coordination'): {TEXT_ONLY},
    ('pubtator_fbk', 'elliptic-coordination'): {TEXT_ONLY},
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
    parsed = bconv.load(path, fmt, id=path.stem)
    _validate(parsed, fmt, expected)


@pytest.mark.parametrize('fmt,path', get_cases(bconv.LOADERS), ids=path_id)
def test_loads(fmt, path, expected):
    """Test the loads function."""
    with xopen(path, fmt) as f:
        parsed = bconv.loads(f.read(), fmt, id=path.stem)
    _validate(parsed, fmt, expected)


@pytest.mark.parametrize('fmt,path', get_cases(bconv.FETCHERS), ids=path_id)
def test_fetch(fmt, path, expected, monkeypatch):
    """Test the fetch function."""
    def _mock_response(_):
        return open(path, 'rb')
    monkeypatch.setattr(urllib.request, 'urlopen', _mock_response)
    parsed = bconv.fetch('ignored', fmt, id=path.stem)
    _validate(parsed, fmt, expected)


def _validate(parsed, fmt, expected):
    restrictions = set(RESTRICTIONS.get(fmt, ()))
    restrictions.update(RESTRICTIONS.get(parsed.id, ()))
    restrictions.update(RESTRICTIONS.get((fmt, parsed.id), ()))
    text = _get_text(parsed)
    exp = expected[parsed.id]
    ref = exp['text']
    if STRIP_WS in restrictions:
        text = _nested_sentences(text, str.strip)
        ref = _nested_sentences(ref, str.strip)
    if UNNEST:
        text = _unnest(text)
        ref = _unnest(ref)
    assert text == ref

    if TEXT_ONLY in restrictions:
        return
    ref = exp['entities']
    if SKIP_CUI in restrictions:
        ref = [list(_skip_cui(doc)) for doc in ref]
    if STR_IDS in restrictions:
        ref = [list(_entity_str_ids(doc)) for doc in ref]
    assert _get_entities(parsed) == ref

    if NO_RELS in restrictions:
        return
    ref = exp.get('relations') or [[] for _ in exp['text']]
    if STR_IDS in restrictions:
        ref = [list(_rel_str_ids(doc)) for doc in ref]
    if BIN_REL_ONLY in restrictions:
        ref = [list(_rel_subj_obj(doc)) for doc in ref]
    assert _get_relations(parsed) == ref


def _get_text(content):
    return _nested_sentences(content.units('document'), lambda sent: sent.text)


def _nested_sentences(docs, call):
    return [[[call(sent) for sent in sec] for sec in doc] for doc in docs]


def _unnest(docs):
    return [[sent for sec in doc for sent in sec] for doc in docs]


def _get_entities(content):
    return [[[_entity_attribute(entity, att) for att in entity.__slots__]
             for entity in doc.iter_entities()]
            for doc in content.units('document')]


def _entity_attribute(entity, att):
    value = getattr(entity, att)
    # Cast offset tuples to list for compatibility with JSON.
    if att == 'spans':
        value = [list(o) for o in value]
    return value


def _get_relations(content):
    return [[{'id': rel.id, 'meta': rel.metadata, 'members': list(map(list, rel))}
             for rel in doc.iter_relations()]
            for doc in content.units('document')]


def _skip_cui(entities):
    for *entity, meta in entities:
        meta = {k: v for k, v in meta.items() if k != 'cui'}
        yield [*entity, meta]


def _entity_str_ids(entities):
    for id_, *entity in entities:
        yield [str(id_), *entity]


def _rel_str_ids(relations):
    for rel in relations:
        yield dict(
            rel,
            id=str(rel['id']),
            members=[[str(refid), role] for refid, role in rel['members']]
        )


def _rel_subj_obj(relations):
    for rel in relations:
        members = zip(rel['members'], ('subj', 'obj'))
        yield dict(
            rel,
            members=[[refid, role] for (refid, _), role in members]
        )
