"""
Formatter base classes.
"""


__author__ = "Lenz Furrer"


import io
from pathlib import Path

from lxml import etree

from ..util.misc import timestamp


class Formatter:
    """
    Base class for all formatters.
    """

    ext = None  # type: str
    binary = False  # text or binary file mode?

    def export(self, content, dest='.'):
        """
        Write this content to disk.
        """
        with self._open(Path(dest), content) as stream:
            self.write(content, stream)

    def _open(self, dest, content):
        if dest.is_dir():
            basename = content.id or content.filename or timestamp()
            dest = Path(dest, '{}.{}'.format(basename, self.ext))
        elif not dest.parent.exists():
            # Use exist_ok because of potential race conditions.
            dest.parent.mkdir(parents=True, exist_ok=True)
        if self.binary:
            return open(file=dest, mode='wb')
        else:
            return open(file=dest, mode='w', encoding='utf8')

    def write(self, content, stream):
        """
        Write this content to an open file.
        """
        raise NotImplementedError()

    def dump(self, content, stream):  # alias for write()
        """
        Write this content to an open file.
        """
        return self.write(content, stream)

    def dumps(self, content):
        """
        Serialise the content to str or bytes.
        """
        raise NotImplementedError()


class MemoryFormatter(Formatter):
    """
    Abstract formatter with a primary dumps method.

    Subclasses must override dumps(), on which write() is based.
    """

    def write(self, content, stream):
        stream.write(self.dumps(content))


class StreamFormatter(Formatter):
    """
    Abstract formatter with a primary write method.

    Subclasses must override write(), on which dumps() is based.
    """

    def dumps(self, content):
        if self.binary:
            buffer = io.BytesIO()
        else:
            buffer = io.StringIO()
        self.write(content, buffer)
        return buffer.getvalue()


class XMLMemoryFormatter(MemoryFormatter):
    """
    Formatter for XML-based output.

    Subclasses must define a method _dump_tree() which returns
    an lxml.etree.Element node.
    """

    ext = 'xml'
    binary = True

    def dumps(self, content):
        node = self._dump_tree(content)
        return self._tostring(node)

    def _dump_tree(self, content):
        raise NotImplementedError()

    @staticmethod
    def _tostring(node, **kwargs):
        kwargs.setdefault('encoding', "UTF-8")
        kwargs.setdefault('xml_declaration', True)
        kwargs.setdefault('pretty_print', True)
        return etree.tostring(node, **kwargs)


class EntityFormatter:
    """
    Mix-in for formats with entity annotations.

    This mix-in class provides two options to control
    simplification (flattening) of entity annotations:
    `avoid_gaps` (suppress discontinuous spans) and
    `avoid_overlaps` (suppress collisions).
    """

    def __init__(self, *args, avoid_gaps=None, avoid_overlaps=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.avoid_gaps = avoid_gaps
        self.avoid_overlaps = avoid_overlaps

    def iter_entities(self, unit):
        """
        Iterate over (potentially modified) entities in unit.
        """
        return unit.iter_entities(avoid_gaps=self.avoid_gaps,
                                  avoid_overlaps=self.avoid_overlaps)


class ContinuousEntityFormatter(EntityFormatter):
    """
    Mix-in for formats with gap-free entity annotations.

    This mix-in class requires the `avoid_gaps` option to
    be different from None.
    """

    def __init__(self, *args, avoid_gaps='split', **kwargs):
        if avoid_gaps is None:
            raise ValueError('avoid_gaps cannot be None; choose from {}'
                             .format('split fill first last'.split()))
        super().__init__(*args, avoid_gaps=avoid_gaps, **kwargs)
