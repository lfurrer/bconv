"""
Loaders and formatters for BioC (XML and JSON).
"""


__author__ = "Lenz Furrer"

__all__ = ['BioCXMLLoader', 'BioCJSONLoader',
           'BioCXMLFormatter', 'BioCJSONFormatter']


import os
import json
from collections import OrderedDict

from lxml import etree
from lxml.builder import E

from ..doc.document import Collection, Document, Entity
from ._load import CollLoader, text_node, wrap_in_collection
from ._export import Formatter, XMLMemoryFormatter, StreamFormatter
from ..util.iterate import peek, json_iterencode
from ..util.misc import iter_codepoint_indices_utf8, iter_byte_indices_utf8
from ..util.stream import text_stream, basename


class _OffsetMixin:
    """
    Mixin for byte-offset handling.
    """

    def _offset_mngr(self):
        if isinstance(self, _BioCLoader):
            fmt = 'xml' if isinstance(self, BioCXMLLoader) else 'json'
            if self.byte_offsets:
                return ByteOffsetReader(fmt)
            else:
                return OffsetReader(fmt)
        else:
            if self.byte_offsets:
                return ByteOffsetWriter()
            else:
                return OffsetWriter()


class _BioCLoader(CollLoader, _OffsetMixin):
    """
    Base class for BioC parsing.

    Currently, any existing relation nodes are discarded.
    """

    def __init__(self, byte_offsets=True):
        super().__init__()
        self.byte_offsets = byte_offsets

    def collection(self, source, id_):
        coll_node, docs = self._parse_collection(source)
        collection = Collection(id_, basename(source))
        collection.metadata = self._meta_dict(coll_node)
        for doc in docs:
            collection.add_document(self._document(doc))
        return collection

    def _parse_collection(self, source):
        raise NotImplementedError

    def _document(self, node):
        """
        Read a document node into a document.Document object.
        """
        doc = Document(self._text(node, 'id', ifnone=None))
        doc.metadata = self.infon_dict(node)

        offset_mngr = self._offset_mngr()
        for passage in self._iterfind(node, 'passage'):
            sec_type, text, offset, infon, anno = self._section(passage,
                                                                offset_mngr)
            doc.add_section(sec_type, text, offset, anno)
            section = doc[-1]
            section.metadata = infon
            # Get infon elements on sentence level.
            for sent, sent_node in zip(section,
                                       self._iterfind(passage, 'sentence')):
                sent.metadata = self.infon_dict(sent_node)

        return doc

    def _section(self, node, offset_mngr):
        """Get all relevant data from a passage node."""
        infon = self.infon_dict(node)
        type_ = infon.get('type')
        text = self._text(node)
        if not text:
            # Text and annotations at sentence level.
            offset = offset_mngr.start(node)
            text, anno = [], []
            for sent in self._iterfind(node, 'sentence'):
                text.append(self._sentence(sent, offset_mngr))
                anno.extend(self._get_annotations(sent, offset_mngr))
        else:
            # Text and annotations at passage level.
            offset = offset_mngr.update(node, text)
            anno = list(self._get_annotations(node, offset_mngr))
        return type_, text, offset, infon, anno

    def _sentence(self, node, offset_mngr):
        """Get text and offset from a sentence node."""
        text = self._text(node)
        offset = offset_mngr.update(node, text)
        return text, offset

    def _get_annotations(self, node, offset_mngr):
        """
        Iterate over annotations.

        Any non-contiguous annotation is split up into
        multiple contiguous annotations.
        """
        for anno in self._iterfind(node, 'annotation'):
            for loc in self._iterfind(anno, 'location'):
                start, length = (int(loc.get(n)) for n in ('offset', 'length'))
                end = offset_mngr.character(start+length)
                start = offset_mngr.character(start)
                yield self._entity(anno, start, end)

    def _entity(self, anno, start, end):
        """Create an Entity instance from a BioC annotation node."""
        id_ = anno.get('id')
        text = self._text(anno)
        info = self.infon_dict(anno)
        return Entity(id_, text, start, end, info)

    def _meta_dict(self, node):
        """Read metadata into a dictionary."""
        meta = {n: self._text(node, n) for n in ('source', 'date', 'key')}
        meta.update(self.infon_dict(node))
        return meta

    def infon_dict(self, node):
        """Read all infon nodes into a dictionary."""
        raise NotImplementedError

    def _iterfind(self, node, query):
        raise NotImplementedError

    def _text(self, node, query='text', onerror=None, ifnone=''):
        raise NotImplementedError


class BioCXMLLoader(_BioCLoader):
    """
    Parser for BioC XML.
    """

    def _parse_collection(self, source):
        first, docs = peek(self._iterparse(source))
        coll_node = first.getparent()
        return coll_node, docs

    def iter_documents(self, source):
        for doc in self._iterparse(source):
            yield self._document(doc)

    @staticmethod
    def _iterparse(source):
        if isinstance(source, os.PathLike):
            source = str(source)
        for _, node in etree.iterparse(source, tag='document'):
            yield node
            node.clear()

    def infon_dict(self, node):
        return {n.attrib['key']: n.text for n in self._iterfind(node, 'infon')}

    @staticmethod
    def _iterfind(node, query):
        return node.iterfind(query)

    @staticmethod
    def _text(node, query='text', onerror=None, ifnone=''):
        return text_node(node, query, onerror=onerror, ifnone=ifnone)


class BioCJSONLoader(_BioCLoader):
    """
    Parser for BioC JSON.
    """

    @staticmethod
    def _parse_collection(source):
        """
        Read BioC JSON into a document.Collection object.
        """
        with text_stream(source) as f:
            coll_node = json.load(f)
        return coll_node, coll_node['documents']

    @staticmethod
    def infon_dict(node):
        return node.get('infons', {})

    @staticmethod
    def _iterfind(node, query):
        return iter(node[query + 's'])

    @staticmethod
    def _text(node, query='text', onerror=None, ifnone=''):
        try:
            text = node[query]
        except KeyError:
            text = onerror
        else:
            if text is None:
                text = ifnone
        return text


class _BioCFormatter(Formatter):
    """
    Base class for BioC formatting.
    """

    def __init__(self, byte_offsets=True, sentence_level=False, metadata=None):
        super().__init__()
        self.byte_offsets = byte_offsets
        self.sentence_level = sentence_level
        self.metadata = metadata


class BioCXMLFormatter(_BioCFormatter, XMLMemoryFormatter, _OffsetMixin):
    """
    BioC XML output format.
    """

    doctype = '<!DOCTYPE collection SYSTEM "BioC.dtd">'

    def write(self, content, stream):
        if isinstance(content, Collection):
            # For their size, serialise collections in a memory-friendly way.
            # The downside is that indentation isn't perfect.
            stream.writelines(self._iter_bytes(content))
        else:
            super().write(content, stream)

    def _dump_tree(self, content):
        coll = wrap_in_collection(content)
        return self._collection(coll)

    def _tostring(self, node, **kwargs):
        kwargs.setdefault('doctype', self.doctype)
        return super()._tostring(node, **kwargs)

    def _iter_bytes(self, coll):
        """
        Iterate over fragments of serialised BioC bytes.
        """
        # Serialise the top-level node and split off the closing tag.
        frame = self._tostring(self._collection_frame(coll))
        tail = '</collection>\n'.encode('UTF-8')
        head = frame[:-len(tail)]

        # Yield fragment by fragment.
        yield head

        for document in coll:
            node = self._document(document)
            frag = self._tostring(node, doctype=None, xml_declaration=False)
            yield frag

        yield tail

    def _collection(self, coll):
        node = self._collection_frame(coll)
        for document in coll:
            node.append(self._document(document))
        return node

    def _collection_frame(self, coll):
        meta = self.metadata
        if meta is None:
            meta = coll.metadata

        node = E('collection',
                 E('source', meta.get('source', '')),
                 E('date', meta.get('date', '')),
                 E('key', meta.get('key', '')))

        for key, value in meta.items():
            if key not in ('source', 'date', 'key'):
                self._infon(node, key, value)

        return node

    def _document(self, doc):
        node = E('document', E('id', str(doc.id)))
        self._add_meta(node, doc.metadata)

        offset_mngr = self._offset_mngr()
        for section in doc:
            node.append(self._passage(section, offset_mngr))

        return node

    def _passage(self, section, offset_mngr):
        node = E('passage')
        self._add_meta(node, section.metadata)
        node.append(E('offset', str(offset_mngr.passage(section))))

        # BioC allows text at sentence or passage level.
        # The annotations are anchored at the same level.
        if self.sentence_level:
            for sent in section:
                node.append(self._sentence(sent, offset_mngr))
        else:
            node.append(E('text', section.text))
            for sent in section:
                offset_mngr.sentence(sent)  # synchronise without direct usage
                self._add_entities(node, sent, offset_mngr)

        return node

    def _sentence(self, sent, offset_mngr):
        node = E('sentence')
        self._add_meta(node, sent.metadata)
        node.append(E('offset', str(offset_mngr.sentence(sent))))
        node.append(E('text', sent.text))

        self._add_entities(node, sent, offset_mngr)

        return node

    def _add_entities(self, node, sent, offset_mngr):
        for entity in sent.iter_entities():
            node.append(self._entity(entity, offset_mngr))

    def _entity(self, entity, offset_mngr):
        node = E('annotation', id=str(entity.id))

        for label, value in entity.info.items():
            self._infon(node, label, value)

        start, length = offset_mngr.entity(entity)
        node.append(E('location', offset=str(start), length=str(length)))

        node.append(E('text', entity.text))

        return node

    def _add_meta(self, node, meta):
        for key, value in meta.items():
            self._infon(node, key, value)

    @staticmethod
    def _infon(node, key, value):
        """
        Add an <infons> element.
        """
        node.append(E('infon', value, key=key))


class BioCJSONFormatter(_BioCFormatter, StreamFormatter, _OffsetMixin):
    """
    BioC JSON output format.
    """

    ext = 'json'

    def write(self, content, stream):
        coll = wrap_in_collection(content)
        prep = self._collection(coll)
        stream.writelines(json_iterencode(prep))

    def _collection(self, coll):
        meta = self.metadata
        if meta is None:
            meta = coll.metadata
        infons = dict(meta)

        return OrderedDict((
            ('source', infons.pop('source', '')),
            ('date', infons.pop('date', '')),
            ('key', infons.pop('key', '')),
            ('infons', infons),
            ('documents', (self._document(d) for d in coll))
        ))

    def _document(self, doc):
        offset_mngr = self._offset_mngr()

        return {
            'id': str(doc.id),
            'infons': dict(doc.metadata),
            'passages': [self._passage(s, offset_mngr) for s in doc],
            'relations': (),
        }

    def _passage(self, section, offset_mngr):
        infons = dict(section.metadata)
        offset = offset_mngr.passage(section)
        text = ''         # empty for sentence-level anchoring
        annotations = []  # empty for sentence-level anchoring
        sentences = []    # empty for passage-level anchoring

        # BioC allows text at sentence or passage level.
        # The annotations are anchored at the same level.
        if self.sentence_level:
            for sent in section:
                sentences.append(self._sentence(sent, offset_mngr))
        else:
            text = section.text
            for sent in section:
                offset_mngr.sentence(sent)  # synchronise without direct usage
                for entity in sent.iter_entities():
                    annotations.append(self._entity(entity, offset_mngr))

        return {
            'infons': infons,
            'offset': offset,
            'text': text,
            'sentences': sentences,
            'annotations': annotations,
            'relations': (),
        }

    def _sentence(self, sent, offset_mngr):
        return {
            'infons': sent.metadata,
            'offset': offset_mngr.sentence(sent),
            'text': sent.text,
            'annotations': [self._entity(e, offset_mngr)
                            for e in sent.iter_entities()],
            'relations': (),
        }

    @staticmethod
    def _entity(entity, offset_mngr):
        start, length = offset_mngr.entity(entity)
        return {
            'id': str(entity.id),
            'infons': dict(entity.info),
            'text': entity.text,
            'locations': [dict(offset=start, length=length)]
        }


class _OffsetManager:
    """
    Abstract base class for offset conversion.
    """

    def start(self, unit):
        """
        Get the converted start offset of this unit.
        """
        # Default: act as a dummy.
        return self._start(unit)

    def update(self, unit, text):
        """
        Process the text of this unit and return its start offset.
        """
        # Default: act as a dummy.
        del text
        return self._start(unit)

    @staticmethod
    def character(index):
        """
        Convert the offset of this character in the current text unit.
        """
        # Default: act as a dummy.
        return index

    def _start(self, unit):
        """
        Get the start offset before conversion.
        """
        raise NotImplementedError


class _OffsetConverter(_OffsetManager):
    """
    Mixin class for non-dummy offset managers.
    """

    def __init__(self):
        # Current difference at the end of the current text unit:
        self._diff = 0  # len(target) - len(source)
        # Start anchors for the current text unit:
        self._cursor_source = None
        self._cursor_target = None
        # Character-level offset mapping for the current text unit:
        self._conv_index = None

    def start(self, unit):
        return self._start(unit) + self._diff

    def update(self, unit, text):
        # Update internal state.
        self._conv_index = list(self._indexer(text))
        self._cursor_source = self._start(unit)
        self._cursor_target = self._cursor_source + self._diff
        len_target = self._conv_index[-1]
        len_source = len(self._conv_index) - 1
        self._diff += len_target - len_source
        return self._cursor_target

    def character(self, index):
        return self._conv_index[index-self._cursor_source]+self._cursor_target

    def _indexer(self, text):
        raise NotImplementedError


class OffsetReader(_OffsetManager):
    """
    Offset forwarding (dummy conversion) for reading BioC.
    """

    def __init__(self, unit_type):
        super().__init__()
        self._start = getattr(self, '_start_{}'.format(unit_type))

    _start = None  # overriden by an instance attribute

    @staticmethod
    def _start_xml(unit):
        # Unit is an lxml element.
        return int(unit.find('offset').text)

    @staticmethod
    def _start_json(unit):
        # Unit is a dict.
        return int(unit['offset'])


class ByteOffsetReader(OffsetReader, _OffsetConverter):
    """
    Offset conversion from bytes to codepoints.
    """

    _indexer = staticmethod(iter_byte_indices_utf8)


class OffsetWriter(_OffsetManager):
    """
    Offset forwarding (dummy conversion) for writing BioC.
    """

    @staticmethod
    def _start(unit):
        # Unit is a bconv.doc.document.Section/Sentence object.
        return unit.start

    @staticmethod
    def entity(entity):
        """
        Calculate start and length of this annotation.
        """
        return entity.start, entity.end-entity.start

    # Aliases for backward compatibility.
    def passage(self, unit):
        """New passage/section: get the start offset."""
        return self.start(unit)

    def sentence(self, unit):
        """New sentence: process the text before returning the start offset."""
        return self.update(unit, unit.text)


class ByteOffsetWriter(OffsetWriter, _OffsetConverter):
    """
    Offset conversion from codepoints to bytes.
    """

    _indexer = staticmethod(iter_codepoint_indices_utf8)

    def entity(self, entity):
        start, end = (self.character(n) for n in (entity.start, entity.end))
        return start, end-start
