"""
Formatter for TSV output (with/without context).
"""


__author__ = "Lenz Furrer"

__all__ = ['CSVFormatter', 'TSVFormatter', 'TextCSVFormatter', 'TextTSVFormatter']


import csv

from ._export import StreamFormatter
from ..util.iterate import CacheOneIter
from ..util.misc import tsv_format


class CSVFormatter(StreamFormatter):
    """
    Compact CSV format for annotations.
    """

    ext = 'csv'

    def __init__(self, fields=(), include_header=False, **fmtparams):
        super().__init__()
        self.extra_fields = fields
        self.include_header = include_header
        self.fmtparams = fmtparams

    def write(self, content, stream):
        writer = csv.writer(stream, **self.fmtparams)

        if self.include_header:
            writer.writerow(self._header())
        for doc in content.units('document'):
            writer.writerows(self._document(doc))

    def _header(self):
        return ('doc_id',
                'section',
                'sent_id',
                'entity_id',
                'start',
                'end',
                'term',
                *self.extra_fields)

    def _document(self, doc):
        # For each token, find all entities starting here.
        # Write a fully-fledged TSV line for each entity.
        # In the text-tsv subclass, also add sparse lines for non-entity tokens.
        for sent_id, sentence in enumerate(doc.units('sentence'), 1):
            toks = CacheOneIter(sentence)
            section_type = sentence.get_section_type(default='')
            loc = doc.id, section_type, sent_id
            last_end = 0  # offset history

            for entity in sentence.iter_entities():
                # Add sparse lines for all tokens preceding the current entity.
                yield from self._tok_rows(last_end, entity.start, toks, loc)
                # Add a rich line for each entity (possibly multiple lines
                # for the same token(s)).
                yield (doc.id,
                       section_type,
                       sent_id,
                       entity.id,
                       entity.start,
                       entity.end,
                       self._entity_text(entity),
                       *self._extra_info(entity))
                last_end = max(last_end, entity.end)
            # Add sparse lines for the remaining tokens.
            yield from self._tok_rows(last_end, float('inf'), toks, loc)

    @staticmethod
    def _entity_text(entity):
        return entity.text

    def _extra_info(self, entity):
        return tuple(entity.info[f] for f in self.extra_fields)

    @staticmethod
    def _tok_rows(start, end, tokens, loc):
        # Subclass hook.
        del start, end, tokens, loc
        return iter(())


class TSVFormatter(CSVFormatter):
    """
    Compact TSV format for annotations.

    This CSV dialect uses tabs for field delimiting,
    Unix line endings as row separators (though this is ulti-
    mately controlled by the caller creating the file handle),
    and no escape mechanism (tabs/newlines in annotations are
    converted to spaces instead).
    """

    ext = 'tsv'

    def __init__(self, fields=(), include_header=False, **fmtparams):
        fmtparams = dict(tsv_format, **fmtparams)
        super().__init__(fields, include_header, **fmtparams)

    @staticmethod
    def _entity_text(entity):
        # TSV has no escape mechanism, therefore use the whitespace-normalized
        # text version, which converts all whitespace to space characters.
        return entity.text_wn


class TextCSVFormatter(CSVFormatter):
    """
    Compact CSV format for annotations and context.
    """

    def __init__(self, fields=(), include_header=False, **fmtparams):
        super().__init__(fields, include_header, **fmtparams)
        self.extra_dummy = ('',) * len(self.extra_fields)

    def _document(self, doc):
        # Make sure all sentences are tokenized.
        for sentence in doc.units('sentence'):
            sentence.tokenize(cache=True)
        return super()._document(doc)

    def _tok_rows(self, start, end, tokens, loc):
        """
        Iterate over tokens within the offset window start..end.
        """
        if start >= end:
            # The window has length 0 (or less).
            return

        doc_id, section_type, sent_id = loc
        for token in tokens:
            if token.start >= end:
                # The token has left the window.
                tokens.repeat()  # rewind the iterator
                break
            if token.end > start:
                # The token is (at least partially) inside the window.
                yield (doc_id,
                       section_type,
                       sent_id,
                       '',
                       token.start,
                       token.end,
                       token.text,
                       *self.extra_dummy)


class TextTSVFormatter(TextCSVFormatter, TSVFormatter):
    """
    Compact TSV format for annotations and context.
    """
