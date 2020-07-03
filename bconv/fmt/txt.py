"""
Loaders and formatter for plain text.
"""


__author__ = "Lenz Furrer"

__all__ = ['TXTLoader', 'TXTJSONLoader', 'TXTFormatter', 'TXTJSONFormatter']


import io
import json

from ._load import DocLoader, DocIterator
from ._export import StreamFormatter
from ..doc.document import Document
from ..util.stream import text_stream, basename


class _TXTLoaderMixin:
    """
    Base loader for plain-text documents.
    """

    def __init__(self, single_section=False, sentence_split=False):
        self.single_section = single_section
        self.sentence_split = sentence_split

    def _document(self, stream, docid):
        if self.single_section:
            # All text in a single section.
            sections = [self._reattach_blank(stream)]
        else:
            # Sections are separated by blank lines.
            sections = []
            for line in self._reattach_blank(stream, signal_boundaries=True):
                if line is None:
                    # Start a new section.
                    sections.append([])
                else:
                    sections[-1].append(line)

        if docid is None:
            # Resort to using the filename as an ID, if available.
            docid = basename(stream)

        doc = Document(docid)
        for text in sections:
            if not self.sentence_split:
                text = ''.join(text)
            doc.add_section('', text)

        return doc

    @staticmethod
    def _reattach_blank(lines, signal_boundaries=False):
        """
        Reattach blank lines to the preceding non-blank line.

        Initial blank lines are prepended to the first non-
        blank line.

        If signal_boundaries is True, the position of the blank
        lines is signaled through yielding None.
        This boundary is always signaled at the beginning, even
        if there are no leading blank lines.
        """
        # Consume all lines until the first non-blank line was read.
        last = ''
        for line in lines:
            last += line
            if line.strip():
                break

        # Unless the input sequence is empty, the first signal is now due.
        if signal_boundaries and last:
            yield None

        # Continue with the rest of the lines.
        # The loop variable is always ahead of the yielded value.
        boundary = False
        for line in lines:
            if not line.strip():
                # Blank line. Don't yield anything, but set a flag for yielding
                # the signal after the current line was yielded.
                boundary = True
                last += line
            else:
                # Non-blank line. Yield what was accumulated.
                yield last
                last = line
                if signal_boundaries and boundary:
                    yield None
                    boundary = False

        # Unless the input sequence was empty, the last line is now due.
        if last:
            yield last


class TXTLoader(DocLoader, _TXTLoaderMixin):
    """
    Loader for single plain-text documents.
    """

    def document(self, source, id_):
        """
        Get a very simply structured document.
        """
        with text_stream(source) as f:
            return self._document(f, id_)


class TXTJSONLoader(DocIterator, _TXTLoaderMixin):
    """
    Loader for multiple plain-text documents embedded in JSON.
    """

    def iter_documents(self, source):
        with text_stream(source) as f:
            docs = json.load(f)

        for doc in docs:
            stream = io.StringIO(doc['text'])
            id_ = doc['id']
            yield self._document(stream, id_)


class TXTFormatter(StreamFormatter):
    """
    Plain text, on which the stand-off annotations are based.
    """

    ext = 'txt'

    @staticmethod
    def write(content, stream):
        stream.writelines(content.iter_text())


class TXTJSONFormatter(StreamFormatter):
    """
    Formatter for multiple plain-text documents embedded in JSON.
    """

    ext = 'json'

    @staticmethod
    def write(content, stream):
        collection = [{'id': doc.id, 'text': doc.text}
                      for doc in content.units('document')]
        json.dump(collection, stream)
