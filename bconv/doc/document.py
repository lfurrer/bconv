"""
Representation of text and annotations.

The structural units are organised into a hierarchy:

    Collection     (optional)
      Document
        Section
          Sentence
            Token  (optional)

There are two types of annotation units:

    Entity
    Relation
      RelationMember

Entities are anchored at the sentence level.
Relations can be anchored at the document, section,
or sentence level, and they have RelationMember units
as their child nodes.
"""


__author__ = "Lenz Furrer"


import re
import logging
from collections import namedtuple
from collections.abc import Sized

from ..util.iterate import peek
from ..nlp.tokenize import TOKENIZER


class SequenceUnit:
    """
    Base class for all non-leaf levels of the document hierarchy.
    """

    _child_type = None  # type: type

    def __init__(self, **metadata):
        super().__init__()
        self._children = []
        self.metadata = metadata

    @property
    def type(self):
        """Dedicated accessor for an important metadata element."""
        return self.metadata.get('type')

    @type.setter
    def type(self, value):
        self.metadata['type'] = value

    def __repr__(self):
        name = self.__class__.__name__
        elems = len(self)
        child_name = self._child_type.__name__.lower()
        plural = '' if elems == 1 else 's'
        address = hex(id(self))
        return ('<{} with {} {}{} at {}>'
                .format(name, elems, child_name, plural, address))

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

    def __init__(self, text=None, **metadata):
        super().__init__(**metadata)
        self._text = text

    @property
    def text(self):
        """Plain-text representation."""
        if self._text is None:
            return ''.join(self.iter_text())
        return self._text

    def units(self, level):
        """
        Iterate over units at any level.

        `level` can be a subtype of Unit, or a case-insensitive
        string of the level name.

        If `level` matches self's level, self is yielded.

        Example:
            my_doc.units("sentence")
        returns a flat iterator over all sentences of a document.
        """
        if isinstance(level, str):
            try:
                level = dict(
                    collection=Collection,
                    document=Document,
                    section=Section,
                    sentence=Sentence,
                    token=Token,
                )[level.lower()]
            except KeyError:
                raise ValueError('unknown unit level: {}'
                                 .format(level))

        if isinstance(self, level):
            # The root level matches.
            yield self

        elif level is self._child_type:
            # Optimisation: avoid recursion for simple iteration
            yield from self._children

        else:
            # Recursively descend into sub-subelements.
            for child in self._children:
                yield from child.units(level)

    def iter_text(self):
        r"""
        Iterate over all text segments, including separators.

        Separator whitespace is reconstructed from offsets,
        using "\n" between sections and " " between sentences.
        """
        raise NotImplementedError

    def iter_entities(self, split_discontinuous=False,
                      avoid_gaps=None, avoid_overlaps=None):
        """
        Iterate over all entities, sorted by start offset.

        If `avoid_gaps` is not None, discontinuous entities
        are turned into contiguous entities through splitting,
        merging, or pruning. Valid values are:
        "split", "fill", "first", "last".

        If `avoid_overlaps` is not None, colliding entities
        are suppressed by keeping only the longest or shortest
        of multiple (partially) co-located entities.
        Value values are: "keep-longer", "keep-shorter"

        The legacy flag `split_discontinuous` is an alias
        for `avoid_gaps="split".
        """
        for sentence in self.units(Sentence):
            yield from sentence.iter_entities(
                split_discontinuous, avoid_gaps, avoid_overlaps)

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
                           e.metadata)
                    for e in entities)
        return entities


class RelationUnit:
    """
    Mix-in for units that can hold relations.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def iter_relations(self):
        """
        Iterate over all relations from this unit and below.
        """
        yield from self.relations
        try:
            for child in self._children:
                yield from child.iter_relations()
        except AttributeError:
            return


# The token-level unit really has no functionality.
Token = namedtuple('Token', 'text start end')


class OffsetUnit(TextUnit, RelationUnit):
    """A unit with start and end offsets."""

    def __init__(self, text, start, end, **metadata):
        super().__init__(text, **metadata)
        self._start = start
        self._end = end

    @property
    def start(self):
        """
        Offset in characters relative to the document start.
        """
        return self._start

    @property
    def end(self):
        """
        End offset in characters relative to the document start.
        """
        return self._end


class Sentence(OffsetUnit):
    """Central annotation unit. """

    _child_type = Token

    def __init__(self, text, section=None, start=0, end=None, **metadata):
        self.section = section
        self.entities = []
        if end is None:
            end = start + len(text)
        super().__init__(text, start, end, **metadata)

    @property
    def text(self):
        return self._text

    def iter_text(self):
        yield self._text

    def __iter__(self):
        self.tokenize(cache=True)
        return super().__iter__()

    def __getitem__(self, index):
        self.tokenize(cache=True)
        return super().__getitem__(index)

    def __len__(self):
        self.tokenize(cache=True)
        return super().__len__()

    def tokenize(self, cache=False):
        """
        Word-tokenize this sentence.

        If `cache` is True and this method has been called
        earlier, it will be skipped this time.
        """
        if self._text and (not self._children or not cache):
            toks = TOKENIZER.tokenize(self.text, self.start)
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
        extracted = [self._text[start-self._start:end-self._start]
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

    def iter_entities(self, split_discontinuous=False,
                      avoid_gaps=None, avoid_overlaps=None):
        if split_discontinuous:
            if avoid_gaps not in (None, 'split'):
                raise ValueError(
                    'legacy flag `split_discontinuous` contradicts '
                    '`avoid_gaps` value {!r}'.format(avoid_gaps))
            avoid_gaps = 'split'

        entities = self.entities
        if avoid_gaps:
            entities = sorted(self._unify_entities(entities, avoid_gaps),
                              key=Entity.sort_key)
        if avoid_overlaps:
            entities = sorted(self._unnest_entities(entities, avoid_overlaps),
                              key=Entity.sort_key)
        return iter(entities)

    def _unify_entities(self, entities, strategy):
        """
        Iterate over entities, unifying discontinuous ones on the fly.
        """
        unify = getattr(self, '_unify_entities_{}'.format(strategy))
        for entity in entities:
            if len(entity.spans) == 1:
                # Contiguous entity -- yield original.
                yield entity
            else:
                # Discontinuous entity -- generate ad-hoc objects.
                for start, end in unify(entity.spans):
                    text = self._text[start-self._start:end-self._end]
                    spans = [(start, end)]
                    yield Entity(entity.id, text, spans, entity.metadata)

    @staticmethod
    def _unify_entities_split(spans):
        return spans

    @staticmethod
    def _unify_entities_fill(spans):
        return [(spans[0][0], spans[-1][1])]

    @staticmethod
    def _unify_entities_first(spans):
        return [spans[0]]

    @staticmethod
    def _unify_entities_last(spans):
        return [spans[-1]]

    def _unnest_entities(self, entities, strategy):
        """
        Iterate over entities, avoiding overlaps through skipping.
        """
        strategy = strategy.replace('-', '_')
        unnest = dict(keep_longer=max, keep_shorter=min)[strategy]
        for overlapping in self._group_overlapping_entities(entities):
            yield unnest(overlapping, key=len)

    @staticmethod
    def _group_overlapping_entities(entities):
        overlapping = []
        end = 0
        for entity in entities:
            if entity.start < end:  # overlaps with previous
                overlapping.append(entity)
            else:                   # no overlap
                if overlapping:
                    yield overlapping
                overlapping = [entity]
            end = max(entity.end, end)
        if overlapping:
            yield overlapping

    def get_section_type(self, default=None):
        """
        Get the type of the superordinate section (if present).
        """
        try:
            return self.section.type
        except AttributeError:  # there is no section
            return default


class Section(OffsetUnit):
    """Any unit of text between document and sentence level."""

    _child_type = Sentence

    def __init__(self, type, text, document, start=0, entities=(), **metadata):
        """
        A section (eg. title, abstract, mesh list).

        The text can be a single string or a list of
        strings (sentences).
        """
        # Adjust text/start/end later.
        super().__init__(text=None, start=start, end=start, **metadata)

        self.type = type
        self.document = document

        if isinstance(text, str):
            # Single string element.
            self._text = text
            sentences = TOKENIZER.split_sentences(text, start)
            sentences = self._merge_sentences_at_entity(sentences, entities)
        else:
            # Iterable of strings or <string, offset...> tuples.
            sentences = self._guess_offsets(text, start)

        self._add_sentences(sentences)
        self.add_entities(entities, offset=0)

    def iter_text(self):
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

    def _add_sentences(self, sentences):
        """
        Add a sequence of sentences with start offsets.
        """
        for sent, *span in sentences:
            self._add_child(Sentence(sent, self, *span))
        if self._children:
            # Adjust the section-level offsets based on the sentences.
            self._start = self._children[0].start
            self._end = self._children[-1].end

    def add_sentence(self, text, offset=None):
        """
        Add a single sentence.
        """
        if offset is None:
            offset = self.end
        sentence = self._guess_offsets((text,), offset)
        self._add_sentences(sentence)
        self._text = None  # no longer valid
        return self[-1]


class Exportable(TextUnit):
    """
    Base class for exportable units (Collection and Document).
    """

    def __init__(self, id, filename=None, **metadata):
        super().__init__(**metadata)
        self.id = id
        self.filename = filename

    def iter_text(self):
        offset = 0
        for section in self.units(Section):
            if offset < section.start:
                # Insert space that was removed between sections.
                yield '\n' * (section.start-offset)
            yield from section.iter_text()
            offset = section.end


class Document(Exportable, RelationUnit):
    """A document with text, metadata and annotations."""

    _child_type = Section

    def add_section(self, type, text, offset=None,
                    entities=(), entity_offset=None, **metadata):
        """
        Append a section to the end.

        The text can be either a str or an iterable of str.
        """
        if offset is None:
            offset = self[-1].end if self else 0
        if entities:
            if entity_offset is None:
                entity_offset = offset
            entities = self._adjust_entity_spans(entities, entity_offset)

        section = Section(type, text, self, offset, entities, **metadata)
        self._add_child(section)
        return section

    def _adjust_entity_spans(self, entities, offset):
        adjusted = super()._adjust_entity_spans(entities, offset)
        # Avoid casting a list (or similar types) to an iterator.
        # Only applies to cases where spans needed to be adjusted.
        if adjusted is not entities and isinstance(entities, Sized):
            adjusted = list(adjusted)
        return adjusted

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

    def __init__(self, id, filename, **metadata):
        super().__init__(id, filename, **metadata)
        self._by_ids = {}

    @classmethod
    def from_iterable(cls, documents, id, filename=None):
        """
        Construct a collection from an iterable of documents.
        """
        coll = cls(id, filename)
        for doc in documents:
            coll.add_document(doc)
        return coll

    def add_document(self, document):
        """
        Add a Document object.
        """
        self._add_child(document)
        self._by_ids[document.id] = document
        return document

    def get_document(self, id):
        """
        Access a document by its ID.
        """
        return self._by_ids[id]

    def iter_relations(self):
        """
        Iterate over all relations from this unit and below.
        """
        for doc in self._children:
            yield from doc.iter_relations()

    # Disabled: can't determine correct location across documents
    add_entities = None


class Entity:
    """
    Link from textual evidence to an annotated entity.
    """

    __slots__ = ('id', 'text', 'spans', 'metadata')

    def __init__(self, id, text, spans, meta=None, **_meta):
        self.id = id
        self.text = text
        self.spans = sorted((start, end) for start, end in spans)
        self.metadata = _meta if meta is None else {**meta, **_meta}

    def __len__(self):
        """Total length in characters."""
        return sum(end - start for start, end in self.spans)

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

    def __init__(self, id, members, **metadata):
        super().__init__(**metadata)
        self.id = id
        for refid, role in members:
            self._add_child(RelationMember(refid, role))

    def __repr__(self):
        return super().__repr__().replace('relationmember', 'member')

    def add_member(self, refid, role):
        """
        Add a member to this relation.
        """
        member = RelationMember(refid, role)
        self._add_child(member)
        return member
