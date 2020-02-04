#!/usr/bin/env python3
# coding: utf8

# Author: Lenz Furrer, 2017--2020


"""
Formatter base classes.
"""


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
        open_params = self._get_open_params(dest, content)
        try:
            stream = open(**open_params)
        except FileNotFoundError:
            # An intermediate directory didn't exist.
            # Create it and try again.
            # (Use exist_ok because of race conditions -- another
            # process might have created it in the meantime.)
            Path(dest).mkdir(exist_ok=True)
            stream = open(**open_params)
        with stream:
            self.write(content, stream)

    def _get_open_params(self, dest, content):
        basename = content.id or content.filename or timestamp()
        path = Path(dest, '{}.{}'.format(basename, self.ext))
        if self.binary:
            return dict(file=path, mode='wb')
        else:
            return dict(file=path, mode='w', encoding='utf8')

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
