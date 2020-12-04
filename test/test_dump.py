"""
Test bconv.dump() and bconv.dumps().
"""


__author__ = "Lenz Furrer"


import io
import json
import tarfile
import zipfile
import itertools as it
from pathlib import Path
from collections import namedtuple

import pytest
from lxml import etree

import bconv
from bconv.doc import document

from .utils import DATA, get_cases, xopen


OPTIONS = {
    # Format-specific options.
    'europepmc': dict(provider='bconv', info=('type', 'cui', 'cui')),
    'europepmc.zip': dict(provider='bconv', info=('type', 'cui', 'cui')),
    'csv': dict(lineterminator='\n'),
    'text_csv': dict(lineterminator='\n'),

    # Document-specific options.
    'sentence-level': dict(sentence_level=True),

    # Both format- and document-specific options.
    ('bionlp', 'CRAFT-example'): dict(att='cui'),
    ('bioc_json', 'CRAFT-example'): dict(sentence_level=True),
    ('bioc_xml', 'CRAFT-example'): dict(sentence_level=True),
}


@pytest.fixture(scope="module")
def internal():
    return {p.stem: _build_internal(p)
            for p in Path(DATA, 'internal').glob('*.json')}


def _build_internal(path):
    with open(path, encoding='utf8') as f:
        data = json.load(f)
    coll = document.Collection(path.stem, path.stem)
    docs = zip(data['ids'], data['text'], data['entities'])
    for id_, text, entities in docs:
        doc = document.Document(id_)
        for sec, tp in zip(text, it.chain(['Title', 'Abstract'],
                                          it.repeat('Section'))):
            doc.add_section(tp, sec)
        doc.add_entities(document.Entity(*e) for e in entities)
        coll.add_document(doc)
    return coll


@pytest.fixture(params=get_cases(bconv.EXPORTERS),
                ids='{0[0]}-{0[1].stem}'.format)
def case(request, internal):
    fmt, path = request.param
    coll = internal[path.stem]
    options = OPTIONS.get(fmt, {})
    options.update(OPTIONS.get(path.stem, {}))
    options.update(OPTIONS.get((fmt, path.stem), {}))
    return Case(fmt, path, coll, options)


Case = namedtuple('Case', 'fmt path coll options')


def test_dump(case):
    f = xopen(None, case.fmt)
    bconv.dump(case.coll, f, case.fmt, **case.options)
    f.seek(0)
    _validate(f, case.fmt, case.path)


def test_dumps(case):
    dump = bconv.dumps(case.coll, case.fmt, **case.options)
    f = xopen(dump, case.fmt)
    _validate(f, case.fmt, case.path)


def _validate(to_test, fmt, path):
    if fmt.endswith('xml'):
        parse = _xml_nodes
    elif fmt == 'txt.json':
        parse = _txt_json
    elif fmt.endswith('json'):
        parse = json.load
    elif fmt == 'europepmc':
        parse = _json_lines
    elif fmt == 'europepmc.zip':
        parse = _zip_of_json_lines
    elif fmt == 'pubanno_json.tgz':
        parse = _tar_of_json_docs
    elif fmt == 'txt':  # skip blank lines (needed for test_load as sec sep)
        parse = _non_blank_lines
    else:
        parse = list  # line-wise comparison of file-handles
    with xopen(path, fmt) as ref:
        assert parse(to_test) == parse(ref)


def _txt_json(stream):
    coll = json.load(stream)
    for doc in coll:
        doc['text'] = _non_blank_lines(doc['text'].split('\n'))
    return coll


def _non_blank_lines(lines):
    return [line for line in lines if line.strip()]


def _xml_nodes(stream):
    """Parse XML into a nested list of tuples, for comparison."""
    tree = etree.parse(stream)
    return _xml_node_as_tuple(tree.getroot())


def _xml_node_as_tuple(node):
    return (node.tag,
            node.text if node.text and not node.text.isspace() else None,
            node.attrib,
            [_xml_node_as_tuple(c) for c in node])


def _json_lines(stream):
    return [json.loads(line) for line in stream]


def _zip_of_json_lines(stream):
    members = {}
    with zipfile.ZipFile(stream) as z:
        for info in z.infolist():
            with io.TextIOWrapper(z.open(info), encoding='utf8') as f:
                members[info.filename] = _json_lines(f)
    return members


def _tar_of_json_docs(stream):
    members = {}
    with tarfile.open(fileobj=stream) as t:
        for info in t:
            with io.TextIOWrapper(t.extractfile(info), encoding='utf8') as f:
                members[info.name] = json.load(f)
    return members
