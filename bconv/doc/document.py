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


class Unit:
    """
    Base class for all levels of representation.
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
                    # entity=Entity,
                )[type_.lower()]
            except KeyError:
                raise ValueError('unknown unit type: {}'
                                 .format(type_))

        if isinstance(self, type_):
            # The root level matches.
            yield self

        # elif type_ is Entity:
        #     # Special case: annotations aren't in self._children.
        #     for sentence in self.units(Sentence):
        #         yield from sentence.entities

        elif type_ is self._child_type:
            # Optimisation: avoid recursion for simple iteration
            yield from self._children

        else:
            # Recursively descend into sub-subelements.
            for child in self._children:
                yield from child.units(type_)

    def iter_entities(self):
        """
        Iterate over all entities, sorted by start offset.
        """
        for sentence in self.units(Sentence):
            yield from sentence.entities

    def add_entities(self, entities):
        """
        Locate the right sentences to anchor entities.
        """
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
                sent.add_entities((entity,))
        except StopIteration:
            logging.warning('annotations outside character range')


# The token-level unit really has no functionality.
Token = namedtuple('Token', 'text start end')


class Sentence(Unit):
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
            self._children = [Token(t, s, e) for t, s, e in toks]

    def add_entities(self, entities):
        """
        Add entities and sort the results by offsets.
        """
        prev_len = len(self.entities)
        for entity in entities:
            term = self.text[entity.start-self.start:entity.end-self.start]
            assert entity.text == term, \
                'entity mention mismatch: {} vs. {}'.format(entity.text, term)
            self.entities.append(entity)

        if prev_len and len(self.entities) > prev_len:
            # If the new annotations weren't the first ones, then they need
            # to be sorted in.
            self.entities.sort(key=Entity.sort_key)

    def iter_entities(self):
        """
        Iterate over all entities, sorted by occurrence.
        """
        yield from self.entities

    def get_section_type(self, default=None):
        """
        Get the type of the superordinate section (if present).
        """
        try:
            return self.section.type
        except AttributeError:  # there is no section
            return default


class Section(Unit):
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
        self.add_entities(entities)

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


class Exportable(Unit):
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

    def add_section(self, section_type, text, offset=None, entities=()):
        """
        Append a section to the end.

        The text can be either a str or an iterable of str.
        """
        if offset is None:
            offset = self._char_cursor
        section = Section(section_type, text, self, offset, entities)
        self._add_child(section)
        self._char_cursor = section.end


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


class Entity(object):
    """
    Link from textual evidence to an annotated entity.
    """

    __slots__ = ('id', 'text', 'start', 'end', 'info')

    def __init__(self, id_, text, start, end, info):
        self.id = id_
        self.text = text
        self.start = start
        self.end = end
        self.info = info  # type: Dict[str, str]

    @property
    def text_wn(self):
        """Whitespace normalised text: replace newlines and tabs."""
        return re.sub(r'\s', ' ', self.text)

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
