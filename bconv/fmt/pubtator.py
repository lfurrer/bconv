"""
Loader and formatter for the PubTator format.
"""


__author__ = "Lenz Furrer"

__all__ = ['PubTatorLoader', 'PubTatorFBKLoader',
           'PubTatorFormatter', 'PubTatorFBKFormatter']


import csv
import itertools as it

from ._load import CollLoader
from ._export import StreamFormatter
from ..doc.document import Collection, Document, Entity
from ..util.misc import tsv_format
from ..util.stream import text_stream, basename


class PubTatorLoader(CollLoader):
    """
    Load PubTator documents.
    """

    _section_labels = {'t': 'Title', 'a': 'Abstract'}

    def __init__(self, info=('type', 'cui')):
        (self.type,
         self.cui) = info

    def collection(self, source, id_):
        entity_counter = it.count(1)
        docs = self._iter_documents(source, entity_counter)
        return Collection.from_iterable(docs, id_, basename(source))

    def iter_documents(self, source):
        return self._iter_documents(source)

    def _iter_documents(self, source, entity_counter=None):
        with text_stream(source) as f:
            for doc_lines in self._split(f):
                yield self._document(doc_lines, entity_counter)

    @staticmethod
    def _split(stream):
        doc_lines = []
        for line in stream:
            if line.strip():
                doc_lines.append(line)
            elif doc_lines:
                yield doc_lines
                doc_lines = []
        if doc_lines:
            yield doc_lines

    def _document(self, lines, entity_counter):
        if entity_counter is None:
            entity_counter = it.count(1)
        docid, sections, anno = self._parse(lines, entity_counter)
        doc = Document(docid)
        for label, text in sections:
            doc.add_section(label, text, entities=iter(anno))
        doc.add_entities(anno)
        return doc

    def _parse(self, lines, entity_counter):
        docid = None
        sections = []
        anno = []
        for line in lines:
            sep = self._separator(line, docid)
            docid, *fields = line.split(sep)
            if sep == '|' and not anno:
                sections.append(self._section(fields))
            elif sep == '\t' and sections and 3 <= len(fields) <= 5:
                if len(fields) == 3:
                    # Relation annotations are silently ignored.
                    continue
                fields[-1] = fields[-1].rstrip('\n\r')
                anno.append(self._entity(entity_counter, *fields))
            else:
                raise ValueError('invalid format: doc {}, line:\n{}'
                                 .format(docid, line))
        return docid, sections, anno

    @staticmethod
    def _separator(line, docid):
        if docid is None:
            return '|'

        i = len(docid)
        if line[:i] != docid:
            raise ValueError('inconsistent document IDs ({}, {})'
                             .format(docid, line[:i]))
        return line[i]

    def _section(self, fields):
        try:
            label, text = fields
        except ValueError:  # pipe character in text body
            label = fields[0]
            text = '|'.join(fields[1:])
        label = self._section_labels.get(label)
        return label, text

    def _entity(self, ids, start, end, text, type_, cui=None):
        info = {self.type: type_}
        if cui is not None:
            info[self.cui] = cui
        return Entity(next(ids), text, int(start), int(end), info)


class PubTatorFBKLoader(PubTatorLoader):
    """
    Load FBK-flavored PubTator documents.
    """

    def __init__(self, info='type'):
        super().__init__([info, None])
        del self.cui

    def _entity(self, _, id_, type_, start, end, text):
        try:
            id_ = int(id_.lstrip('T'))
        except ValueError:
            pass
        info = {self.type: type_}
        return Entity(id_, text, int(start), int(end), info)


class PubTatorFormatter(StreamFormatter):
    """
    Create a mixture of pipe- and tab-separated plain-text.
    """

    ext = 'txt'

    def __init__(self, info=('type', 'cui')):
        (self.type,
         self.cui) = info

    def write(self, content, stream):
        tsv = csv.writer(stream, **tsv_format)
        first = True
        for doc in content.units('document'):
            if first:
                first = False
            else:
                stream.write('\n')
            self._write_document(stream, tsv, doc)

    def _write_document(self, stream, tsv, document):
        try:
            # Make sure the spans are relative to the start of the document.
            offset = -1 * next(document.units('sentence')).start
        except StopIteration:
            # Empty document (no sentences).
            offset = 0

        annotations = []
        for sec in document:
            text = self._single_line(sec.text)
            stream.write(self._textline(document.id, sec.type, text))
            annotations.extend(self._annotations(document.id, sec, offset))
            offset += len(text) - len(sec.text)
        tsv.writerows(annotations)

    @staticmethod
    def _single_line(text):
        """Remove internal newlines and trailing whitespace."""
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        text = text.rstrip()
        text = text + '\n'
        return text

    @staticmethod
    def _textline(id_, type_, text):
        id_ = id_ if id_ else 'unknown'
        t = type_[0].lower() if type_ else 'x'
        return '|'.join((id_, t, text))

    def _annotations(self, docid, sec, offset):
        for entity in sec.iter_entities():
            start, end = entity.start+offset, entity.end+offset
            yield self._select_anno_fields(docid, start, end, entity)

    def _select_anno_fields(self, docid, start, end, entity):
        return (docid, start, end, entity.text_wn,
                entity.info[self.type], entity.info[self.cui])


class PubTatorFBKFormatter(PubTatorFormatter):
    """
    FBK flavor of the PubTator format.
    """

    def __init__(self, info='type'):
        super().__init__([info, None])
        del self.cui

    def _select_anno_fields(self, docid, start, end, entity):
        try:
            id_ = int(entity.id)
        except ValueError:
            id_ = entity.id
        else:
            id_ = 'T{}'.format(id_)
        return (docid, id_, entity.info[self.type], start, end, entity.text)
