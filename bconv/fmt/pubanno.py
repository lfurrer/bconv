"""
Formatter for PubAnnotation JSON output.

http://www.pubannotation.org/docs/annotation-format/
"""


__author__ = "Nicola Colic, Lenz Furrer"

__all__ = ['PubAnnoJSONFormatter', 'PubAnnoTGZFormatter']


import io
import json
import time
import tarfile

from ._export import Formatter, StreamFormatter
from ..doc.document import Collection, Document, Section
from ..util.iterate import pids


class PubAnnoJSONFormatter(Formatter):
    """
    PubAnnotation JSON format.
    """

    ext = 'json'

    def __init__(self, obj='type', sourcedb=None, **meta):
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
        for entity, tid in zip(content.iter_entities(), pids('T')):
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
        for entity, tid in zip(content.iter_entities(), pids('T')):
            for key, value in entity.metadata.items():
                if key != self.obj:
                    yield {
                        'id': next(att_ids),
                        'subj': tid,
                        'pred': key,
                        'obj': value,
                    }

    @staticmethod
    def _relations(content):
        refs = {
            a.id: pid
            for annos, prefix in ((content.iter_entities(), 'T'),
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
