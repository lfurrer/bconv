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

    def export(self, content, dir_='.'):
        """
        Write this content to disk.
        """
        open_params = self._get_open_params(dir_, content)
        try:
            stream = open(**open_params)
        except FileNotFoundError:
            # An intermediate directory didn't exist.
            # Create it and try again.
            # (Use exist_ok because of race conditions -- another
            # process might have created it in the meantime.)
            Path(dir_).mkdir(exist_ok=True)
            stream = open(**open_params)
        with stream:
            self.write(stream, content)

    def _get_open_params(self, dir_, content):
        basename = content.id or content.filename or timestamp()
        path = Path(dir_, '{}.{}'.format(basename, self.ext))
        if self.binary:
            return dict(file=path, mode='wb')
        else:
            return dict(file=path, mode='w', encoding='utf8')

    def write(self, stream, content):
        """
        Write this content to an open file.
        """
        raise NotImplementedError()

    def dump(self, content):
        """
        Serialise the content to str or bytes.
        """
        raise NotImplementedError()


class MemoryFormatter(Formatter):
    """
    Abstract formatter with a primary dump method.

    Subclasses must override dump(), on which write() is based.
    """

    def write(self, stream, content):
        stream.write(self.dump(content))


class StreamFormatter(Formatter):
    """
    Abstract formatter with a primary write method.

    Subclasses must override write(), on which dump() is based.
    """

    def dump(self, content):
        if self.binary:
            buffer = io.BytesIO()
        else:
            buffer = io.StringIO()
        self.write(buffer, content)
        return buffer.getvalue()


class XMLMemoryFormatter(MemoryFormatter):
    """
    Formatter for XML-based output.

    Subclasses must define a method _dump() which returns
    an lxml.etree.Element node.
    """

    ext = 'xml'
    binary = True

    def dump(self, content):
        node = self._dump(content)
        return self._tostring(node)

    def _dump(self, content):
        raise NotImplementedError()

    @staticmethod
    def _tostring(node, **kwargs):
        kwargs.setdefault('encoding', "UTF-8")
        kwargs.setdefault('xml_declaration', True)
        kwargs.setdefault('pretty_print', True)
        return etree.tostring(node, **kwargs)
