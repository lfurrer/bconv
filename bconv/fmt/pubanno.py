"""
Formatter for PubAnnotation JSON output.

http://www.pubannotation.org/docs/annotation-format/
"""


__author__ = "Nicola Colic, Lenz Furrer"

__all__ = ['PubAnnoJSONLoader', 'PubAnnoTGZLoader',
           'PubAnnoJSONFormatter', 'PubAnnoTGZFormatter']


import io
import json
import time
import tarfile
import warnings
import itertools as it
from collections import defaultdict
from contextlib import contextmanager

from ._load import DocLoader, DocIterator
from ._export import Formatter, StreamFormatter, EntityFormatter
from ..doc.document import Collection, Document, Section, Entity, Relation
from ..util.iterate import pids
from ..util.stream import text_stream, bin_stream, basename


class _PubAnnoLoader:
    """
    Load a document in PubAnnotation format.
    """

    def __init__(self, obj='type'):
        self.obj = obj
        # Map file-local prefixed IDs ('T1', 'T2, 'R1', etc.)
        # to doc-local unprefixed integer IDs (1, 2, 3 etc.).
        self._ids = None

    def _reset_ids(self, keep_counter=False):
        if keep_counter and self._ids is not None:
            self._ids.clear()
        else:
            self._ids = defaultdict(it.count(1).__next__)

    def _add_section(self, doc, text='',
                     denotations=(), attributes=(), relations=(), **_ignored):
        entities, relations = self._annotations(
            denotations, attributes, relations, text)
        sec = doc.add_section('', text, entities=entities)
        sec.relations = relations

    def _annotations(self, denotations, attributes, relations, text):
        entities = {e.id: e for e in self._entities(denotations, text)}
        self._insert_attributes(entities, attributes)
        relations = list(self._relations(entities, relations, text))
        return entities.values(), relations

    def _entities(self, denotations, text):
        with rephrase_keyerror('denotation', ('id', 'span', 'obj')):
            for deno in denotations:
                tid = self._ids[deno['id']]
                obj = deno['obj']
                spans = deno['span']
                if not isinstance(spans, list):
                    spans = [spans]
                spans = [(s['begin'], s['end']) for s in spans]
                term = self._get_term(text, spans)
                yield Entity(tid, term, spans, {self.obj: obj})

    def _insert_attributes(self, entities, attributes):
        with rephrase_keyerror('attribute', ('subj', 'pred', 'obj')):
            for att in attributes:
                tid = self._ids[att['subj']]
                key = att['pred']
                value = att['obj']
                entities[tid].metadata[key] = value

    def _relations(self, entities, relations, text):
        with rephrase_keyerror('relation', ('id', 'subj', 'pred', 'obj')):
            for rel in relations:
                rid = self._ids[rel['id']]
                subj = self._ids[rel['subj']]
                pred = rel['pred']
                obj = self._ids[rel['obj']]
                if self._is_lexically_chained(pred, entities[obj]):
                    self._merge_entites(entities, subj, obj, text)
                else:
                    members = [(subj, 'subj'), (obj, 'obj')]
                    yield Relation(rid, members, type=pred)

    @staticmethod
    def _get_term(text, spans):
        return ' [...] '.join(text[s:e] for s, e in sorted(spans))

    def _is_lexically_chained(self, pred, entity):
        return (pred == '_lexicallyChainedTo'
                and entity.metadata[self.obj] == '_FRAGMENT')

    def _merge_entites(self, entities, subj, obj, text):
        fragment = entities.pop(obj)
        fragment.metadata.pop(self.obj)
        entity = entities[subj]
        entity.spans = sorted(entity.spans + fragment.spans)
        entity.text = self._get_term(text, entity.spans)
        entity.metadata.update(fragment.metadata)


class PubAnnoJSONLoader(DocLoader, _PubAnnoLoader):
    """
    Load a document in PubAnnotation JSON format.
    """

    def document(self, source, id):
        self._reset_ids()
        with text_stream(source) as f:
            data = json.load(f)
        if id is None:
            id = data.get('sourceid', basename(source))
        doc = Document(id)
        self._add_section(doc, **data)
        return doc


class PubAnnoTGZLoader(DocIterator, _PubAnnoLoader):
    """
    Load documents from an archive of PubAnnotation JSON files.
    """

    def iter_documents(self, source):
        self._reset_ids()
        documents = defaultdict(list)
        for div in self._iter_divs(source):
            docid = div['sourceid']
            documents[docid].append(div)
        for docid, divisions in documents.items():
            doc = Document(docid)
            divisions.sort(key=lambda div: div.get('divid', float('nan')))
            for div in divisions:
                self._add_section(doc, **div)
                self._reset_ids(keep_counter=True)
            yield doc

    @staticmethod
    def _iter_divs(source):
        with bin_stream(source) as b:
            with tarfile.open(fileobj=b, mode='r|*') as tar:
                for info in tar:
                    if info.isfile() and info.name.lower().endswith('.json'):
                        with tar.extractfile(info) as f:
                            with text_stream(f) as t:
                                div = json.load(t)
                        div.setdefault('sourceid', basename(info.name))
                        yield div


class PubAnnoJSONFormatter(Formatter, EntityFormatter):
    """
    PubAnnotation JSON format.
    """

    ext = 'json'

    def __init__(self, obj='type', sourcedb=None,
                 avoid_gaps=None, avoid_overlaps=None, **meta):
        super().__init__(avoid_gaps=avoid_gaps, avoid_overlaps=avoid_overlaps)
        self.obj = obj
        self.meta = {'sourcedb': sourcedb, **meta}

    def write(self, content, stream):
        json.dump(self._prepare(content), stream, indent=2)

    def dumps(self, content):
        return json.dumps(self._prepare(content), indent=2)

    def _prepare(self, content):
        if isinstance(content, Section):
            json_object = self._division(content)
        elif isinstance(content, Document):
            json_object = self._document(content)
        elif isinstance(content, Collection):
            json_object = [self._document(doc) for doc in content]
            if len(json_object) == 1:
                json_object = json_object[0]
            else:
                warnings.warn(
                    'Serialising a collection of documents in a single JSON '
                    'file results in a format which violates the PubAnnotation '
                    'specs and which cannot be loaded back by bconv. '
                    'Please consider using the pubanno_json.tgz format instead.')
        else:
            raise ValueError('Cannot serialise {}'.format(type(content)))
        return json_object

    def _division(self, section, divid=1):
        return self._annotation(section, offset=section.start,
                                sourceid=section.document.id, divid=divid)

    def _document(self, document):
        return self._annotation(document, sourceid=document.id)

    def _annotation(self, content, offset=0, **meta):
        return {
            'text': content.text,
            'denotations': list(self._entities(content, offset)),
            'attributes': list(self._attributes(content)),
            'relations': list(self._relations(content)),
            **meta,
            **self.meta,
        }

    def _entities(self, content, offset):
        for entity, tid in zip(self.iter_entities(content), pids('T')):
            yield {
                'id' : tid,
                'span' : self._spans(entity, offset),
                'obj' : self._concept(entity),
            }

    def _concept(self, entity):
        try:
            return entity.metadata[self.obj]
        except KeyError as e:
            if e.args == (self.obj,):
                raise ValueError(
                    'Need concept object: {!r} not found in Entity.metadata. '
                    'Please check the `obj` option.'
                    .format(self.obj))
            raise

    @staticmethod
    def _spans(entity, offset):
        # Use the bagging model to represent discontinuous annotations.
        spans = [{'begin': start-offset, 'end': end-offset}
                 for start, end in entity.spans]
        if len(spans) == 1:
            # Avoid extended syntax if not necessary.
            return spans[0]
        return spans

    def _attributes(self, content):
        att_ids = pids('A')
        for entity, tid in zip(self.iter_entities(content), pids('T')):
            for key, value in entity.metadata.items():
                if key != self.obj:
                    yield {
                        'id': next(att_ids),
                        'subj': tid,
                        'pred': key,
                        'obj': value,
                    }

    def _relations(self, content):
        refs = {
            a.id: pid
            for annos, prefix in ((self.iter_entities(content), 'T'),
                                  (content.iter_relations(), 'R'))
            for a, pid in zip(annos, pids(prefix))
        }
        for relation, rid in zip(content.iter_relations(), pids('R')):
            try:
                subj, obj = relation
            except ValueError:
                raise ValueError(
                    'PubAnnotation format supports binary relations only; '
                    'found relation with arity {}.'.format(len(relation)))
            yield {
                'id': rid,
                'subj': refs[subj.refid],
                'pred': relation.type,
                'obj': refs[obj.refid],
            }


class PubAnnoTGZFormatter(StreamFormatter, PubAnnoJSONFormatter):
    """
    Gzipped TAR archive with PubAnnotation JSON files.
    """

    ext = 'tgz'
    binary = True

    def write(self, content, stream):
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            for doc in content.units(Document):
                for name, div in self._iter_divs(doc):
                    blob = json.dumps(div, indent=2).encode('utf8')
                    info = tarfile.TarInfo(name)
                    info.size = len(blob)
                    info.mtime = time.time()
                    tar.addfile(info, io.BytesIO(blob))

    def _iter_divs(self, doc):
        if doc.relations:
            # If there are document-level annotations, all sections need to be
            # in the same file (archive member).
            div = self._document(doc)
            name = '{}.json'.format(div['sourceid'])
            yield name, div
        else:
            for divid, sec in enumerate(doc, start=1):
                div = self._division(sec, divid=divid)
                name = '{}-{}.json'.format(div['sourceid'], divid)
                yield name, div


@contextmanager
def rephrase_keyerror(name, keys):
    """
    Catch KeyErrors for `keys` and raise a ValueError instead.
    """
    try:
        yield None
    except KeyError as e:
        if e.args[0] in keys:
            raise ValueError('missing {} entry: {}'.format(name, e.args[0]))
        raise
