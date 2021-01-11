"""
Representation of text and annotations.

The structural units are organised into a hierarchy:

    Collection     (optional)
      Document
        Section
          Sentence
            Token  (optional)
            Entity (optional)

Entities are anchored at the sentence level, but not
as child nodes.
"""


__author__ = "Lenz Furrer"


import re
import logging
from collections import namedtuple

from ..util.iterate import peek
from ..nlp.tokenize import TOKENIZER


class SequenceUnit:
    """
    Base class for all non-leaf levels of the document hierarchy.
    """

    _child_type = None  # type: type

    def __init__(self):
        self._children = []
        self._metadata = None

    @property
    def metadata(self):
        """Metadata imported from input documents."""
        if self._metadata is None:
            self._metadata = {}
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._metadata = value

    @property
    def type(self):
        """Dedicated accessor for an important metadata element."""
        return self.metadata.get('type')

    @type.setter
    def type(self, value):
        self.metadata['type'] = value

    def __repr__(self):
        name = self.__class__.__name__
        elems = len(self._children)
        plural = '' if elems == 1 else 's'
        address = hex(id(self))
        return ('<{} with {} subelement{} at {}>'
                .format(name, elems, plural, address))

    def __iter__(self):
        return iter(self._children)

    def __getitem__(self, index):
        return self._children[index]

    def __len__(self):
        return len(self._children)

    def _add_child(self, child):
        """
        Check for proper type before adding.
        """
        assert isinstance(child, self._child_type)
        self._children.append(child)


class TextUnit(SequenceUnit):
    """
    Base class for units containing text.
    """

    def __init__(self):
        super().__init__()
        self._relations = None

    @property
    def relations(self):
        """Relations anchored at this unit."""
        if self._relations is None:
            self._relations = []
        return self._relations

    @relations.setter
    def relations(self, value):
        relations = list(value)
        assert all(isinstance(r, Relation) for r in relations)
        self._relations = relations

    def units(self, type_):
        """
        Iterate over units at any level.

        `type_` can be a subtype of Unit, or a case-insensitive
        string of the type name.

        If `type_` matches self's type, self is yielded.

        Example:
            my_doc.units("sentence")
        returns a flat iterator over all sentences of a document.
        """
        if isinstance(type_, str):
            try:
                type_ = dict(
                    collection=Collection,
                    document=Document,
                    section=Section,
                    sentence=Sentence,
                    token=Token,
                )[type_.lower()]
            except KeyError:
                raise ValueError('unknown unit type: {}'
                                 .format(type_))

        if isinstance(self, type_):
            # The root level matches.
            yield self

        elif type_ is self._child_type:
            # Optimisation: avoid recursion for simple iteration
            yield from self._children

        else:
            # Recursively descend into sub-subelements.
            for child in self._children:
                yield from child.units(type_)

    def iter_entities(self, split_discontinuous=False):
        """
        Iterate over all entities, sorted by start offset.

        If split_discontinuous is True, entities with multiple
        spans are split into multiple contiguous entities.
        """
        for sentence in self.units(Sentence):
            yield from sentence.iter_entities(split_discontinuous)

    def add_entities(self, entities, offset=None):
        """
        Locate the right sentences to anchor entities.
        """
        entities = self._adjust_entity_spans(entities, offset)
        entities = sorted(entities, key=Entity.sort_key)
        if not entities:
            # Short circuit if possible.
            return

        sentences = self.units(Sentence)
        try:
            sent = next(sentences)
            for entity in entities:
                while entity.start >= sent.end:
                    sent = next(sentences)
                sent.add_entities((entity,), offset=0)
        except StopIteration:
            logging.warning('annotations outside character range')

    def _adjust_entity_spans(self, entities, offset):
        """Add offset to all entity spans, if necessary."""
        if offset is None:
            offset = getattr(self, 'start', 0)  # Document has no start member
        if offset:
            return (Entity(e.id,
                           e.text,
                           [(start+offset, end+offset)
                            for start, end in e.spans],
                           e.info)
                    for e in entities)
        return entities

    def iter_relations(self):
        """
        Iterate over all relations from this unit and below.
        """
        yield from self.relations
        try:
            for child in self:
                yield from child.iter_relations()
        except AttributeError:
            return


# The token-level unit really has no functionality.
Token = namedtuple('Token', 'text start end')


class Sentence(TextUnit):
    """Central annotation unit. """

    _child_type = Token

    def __init__(self, text, section=None, start=0, end=None):
        super().__init__()
        self.text = text
        self.section = section
        self.entities = []
        # Character offsets:
        self.start = start
        self.end = end if end is not None else start + len(text)

    def tokenize(self, cache=False):
        """
        Word-tokenize this sentence.

        If `cache` is True and this method has been called
        earlier, it will be skipped this time.
        """
        if self.text and (not self._children or not cache):
            toks = TOKENIZER.span_tokenize_words(self.text, self.start)
            self.set_tokens(toks)

    def set_tokens(self, tokens):
        """
        Set tokens from a sequence of <token, start, end> triples.

        No validation takes place wrt. offset ranges or text substring.
        The tokens can be cleared with a subsequent call to self.tokenize().
        """
        self._children = [Token(tok, start, end) for tok, start, end in tokens]

    def add_entities(self, entities, offset=None):
        """
        Add entities and sort the results by offsets.
        """
        entities = self._adjust_entity_spans(entities, offset)

        prev_len = len(self.entities)
        for entity in entities:
            self._validate_spans(entity)
            self.entities.append(entity)

        if prev_len and len(self.entities) > prev_len:
            # If the new annotations weren't the first ones, then they need
            # to be sorted in.
            self.entities.sort(key=Entity.sort_key)

    def _validate_spans(self, entity):
        extracted = [self.text[start-self.start:end-self.start]
                     for start, end in entity.spans]
        def _mismatch():
            try:
                docid = self.section.document.id
            except AttributeError:
                docid = None
            ext = extracted[0] if len(extracted) == 1 else extracted
            return ('entity mention mismatch in document {}: {!r} vs. {!r}'
                    .format(docid, entity.text, ext))

        # Checking a contiguous annotation is straight-forward.
        if len(extracted) == 1:
            assert extracted[0] == entity.text, _mismatch()
            return

        # For discontinuous annotations, make sure all extracted spans
        # are part of the text attribute. Apart from that, only allow
        # certain separator symbols that are commonly used to represent
        # the gaps in the original text, such as:
        # - " "
        # - " ... "
        # - " [...] "
        # - " … "  (ellipsis, U+2026)
        separators = ' .[]…'
        text = entity.text
        for span in extracted:
            try:
                start = text.index(span)
            except ValueError:
                raise AssertionError(_mismatch())
            assert text[:start].strip(separators) == '', _mismatch()
            text = text[start+len(span):]
        assert text.strip(separators) == '', _mismatch()

    def iter_entities(self, split_discontinuous=False):
        if split_discontinuous:
            return iter(sorted(self._split_discontinuous_entities(),
                               key=Entity.sort_key))
        else:
            return iter(self.entities)

    def _split_discontinuous_entities(self):
        """
        Iterate over entities, splitting discontinuous ones on the fly.
        """
        for entity in self.entities:
            for start, end in entity.spans:
                if (start, end) == (entity.start, entity.end):
                    # Contiguous entity -- yield original.
                    yield entity
                else:
                    # Discontinuous entity -- generate ad-hoc objects.
                    text = self.text[start-self.start:end-self.end]
                    yield Entity(entity.id, text, [(start, end)], entity.info)

    def get_section_type(self, default=None):
        """
        Get the type of the superordinate section (if present).
        """
        try:
            return self.section.type
        except AttributeError:  # there is no section
            return default


class Section(TextUnit):
    """Any unit of text between document and sentence level."""

    _child_type = Sentence

    def __init__(self, section_type, text, document, start=0, entities=()):
        """
        A section (eg. title, abstract, mesh list).

        The text can be a single string or a list of
        strings (sentences).
        """
        super().__init__()

        self.type = section_type
        self.document = document
        self._text = None
        # Character offsets -- adjusted later through add_sentences().
        self.start = start
        self.end = start

        if isinstance(text, str):
            # Single string element.
            self._text = text
            sentences = TOKENIZER.span_tokenize_sentences(text, start)
            sentences = self._merge_sentences_at_entity(sentences, entities)
        else:
            # Iterable of strings or <string, offset...> tuples.
            sentences = self._guess_offsets(text, start)

        self.add_sentences(sentences)
        self.add_entities(entities, offset=0)

    @property
    def text(self):
        """
        Plain text form for inspection and Brat output.
        """
        if self._text is None:
            self._text = ''.join(self.iter_text())
        return self._text

    def iter_text(self):
        """
        Iterate over sentence text and blanks.
        """
        offset = self.start
        for sent in self._children:
            if offset < sent.start:
                # Insert space that was removed in sentence splitting.
                yield ' ' * (sent.start-offset)
            yield sent.text
            offset = sent.end
        # Check for trailing whitespace.
        if offset < self.end:
            yield ' ' * (self.end-offset)

    @staticmethod
    def _merge_sentences_at_entity(sentences, entities):
        """
        Avoid sentence boundaries in the middle of an entity.
        """
        forbidden = set(i for e in entities for i in range(e.start+1, e.end))
        try:
            pending = next(sentences)
        except StopIteration:  # no sentences -- nothing to do
            return
        for sent, start, end in sentences:
            if start in forbidden:
                # Merge with the pending sentence.
                sent = pending[0] + sent
                start = pending[1]
            else:
                yield pending
            pending = sent, start, end
        yield pending

    @staticmethod
    def _guess_offsets(sentences, offset):
        """
        Inspect the first elem to see if offsets are provided.
        If not, try to substitute them.
        """
        try:
            first, sentences = peek(sentences)
        except StopIteration:
            # Empty iterable.
            return

        if isinstance(first, str):
            # Substitute the offsets.
            for sent in sentences:
                yield sent, offset
                offset += len(sent)
        else:
            # Propagate the sentence/offset tuples.
            yield from sentences

    def add_sentences(self, sentences):
        """
        Add a sequence of sentences with start offsets.
        """
        for sent, *span in sentences:
            self._add_child(Sentence(sent, self, *span))
        if self._children:
            # Adjust the section-level offsets based on the sentences.
            self.start = self._children[0].start
            self.end = self._children[-1].end


class Exportable(TextUnit):
    """
    Base class for exportable units (Collection and Document).
    """

    def __init__(self, id_, filename=None):
        super().__init__()
        self.id = id_
        self.filename = filename

    @property
    def text(self):
        """
        Plain text form for inspection and Brat output.
        """
        return ''.join(self.iter_text())

    def iter_text(self):
        r"""
        Iterate over all text segments, including separators.

        Separator whitespace is reconstructed from offsets,
        using "\n" between sections and " " between sentences.
        """
        offset = 0
        for section in self.units(Section):
            if offset < section.start:
                # Insert space that was removed between sections.
                yield '\n' * (section.start-offset)
            yield from section.iter_text()
            offset = section.end


class Document(Exportable):
    """A document with text, metadata and annotations."""

    _child_type = Section

    def __init__(self, id_, filename=None, type_=None):
        super().__init__(id_, filename)
        self._char_cursor = 0
        if type_ is not None:
            self.type = type_

    def add_section(self, section_type, text, offset=None,
                    entities=(), entity_offset=None):
        """
        Append a section to the end.

        The text can be either a str or an iterable of str.
        """
        if offset is None:
            offset = self._char_cursor
        if entities:
            if entity_offset is None:
                entity_offset = offset
            entities = self._adjust_entity_spans(entities, entity_offset)

        section = Section(section_type, text, self, offset, entities)
        self._add_child(section)
        self._char_cursor = section.end

    def sanitize_relations(self):
        """
        Check reference IDs in relations.

        Raise ValueError if a relation references a non-existent ID.
        """
        ids = {rel.id for rel in self.iter_relations()}
        if not ids:
            return  # short-circuit if there are no relations
        ids.update(entity.id for entity in self.iter_entities())
        ref_ids = {m.refid for rel in self.iter_relations() for m in rel}
        if not ref_ids.issubset(ids):
            raise ValueError('Unknown references in relations: {}'
                             .format(ref_ids.difference(ids)))


class Collection(Exportable):
    """A collection of multiple documents."""

    _child_type = Document

    def __init__(self, id_, filename):
        super().__init__(id_, filename)
        self._by_ids = {}

    @classmethod
    def from_iterable(cls, documents, id_, filename=None):
        """
        Construct a collection from an iterable of documents.
        """
        coll = cls(id_, filename)
        for doc in documents:
            coll.add_document(doc)
        return coll

    def add_document(self, document):
        """
        Add a Document object.
        """
        self._add_child(document)
        self._by_ids[document.id] = document

    def get_document(self, id_):
        """
        Access a document by its ID.
        """
        return self._by_ids[id_]

    # Disabled: can't determine correct location across documents
    add_entities = None


class Entity:
    """
    Link from textual evidence to an annotated entity.
    """

    __slots__ = ('id', 'text', 'spans', 'info')

    def __init__(self, id_, text, spans, info):
        self.id = id_
        self.text = text
        self.spans = spans
        self.info = info  # type: Dict[str, str]

    @property
    def text_wn(self):
        """Whitespace normalised text: replace newlines and tabs."""
        return re.sub(r'\s', ' ', self.text)

    @property
    def start(self):
        """Offset of the first character."""
        return self.spans[0][0]

    @property
    def end(self):
        """Offset of the last character."""
        return self.spans[-1][1]

    @classmethod
    def sort(cls, entities):
        """
        Sort a list of Entity instances by offsets, in-place.
        """
        entities.sort(key=cls.sort_key)

    @staticmethod
    def sort_key(entity):
        """
        Sort entities by offset.
        """
        return entity.start, entity.end


RelationMember = namedtuple('RelationMember', 'refid role')


class Relation(SequenceUnit):
    """
    Link between multiple entities and/or other relations.
    """

    _child_type = RelationMember

    def __init__(self, id_, members):
        super().__init__()
        self.id = id_
        for refid, role in members:
            self._add_child(RelationMember(refid, role))
