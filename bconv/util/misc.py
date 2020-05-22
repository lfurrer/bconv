"""
Miscellaneous utilities.
"""


__author__ = "Lenz Furrer"


import time
import codecs


def timestamp():
    """A dense, human-readable timestamp of the local time."""
    return time.strftime('%Y%m%d-%H%M%S')


# CSV flavour for reading and writing TSV files.
# Treat every character literally (including quotes).
tsv_format = dict(
    lineterminator='\n',  # ignored by csv.reader
    delimiter='\t',
    quotechar=None,
)


def codepoint_indices(text, codec, text2bytes=True):
    """
    Create a mapping from text to byte offsets, or vice versa.

    If text2bytes is True, create a list of integers where
    each position corresponds to the position of a codepoint
    in `text`, and each value corresponds to the offset of
    the first byte that encodes this character in the octet
    sequence, when using the given `codec`.
    If text2bytes is False, the list maps from byte offsets
    to codepoint offsets.
    In both cases, `text` is a decoded str.

    The returned list has a length of `len(text)+1` or `len(octets)+1`,
    as it includes the end offset as well.
    """
    # Use UTF-8 optimisation if applicable.
    if codecs.lookup(codec).name == 'utf-8':  # lookup: get canonical spelling
        if text2bytes:
            indices = iter_codepoint_indices_utf8(text)
        else:
            indices = iter_byte_indices_utf8(text)
    else:
        if text2bytes:
            indices = iter_codepoint_indices(text, codec)
        else:
            indices = iter_byte_indices(text, codec)
    return list(indices)

def iter_codepoint_indices(text, codec):
    """
    Iterate over the byte offset of each character (any codec).
    """
    # Note: for encodings with a BOM, the first offset probably shouldn't
    # be 0, but 2, 3, or 4, depending on the BOM's length.
    # This is ignored due to the lack of expected practical applications.
    i = 0
    for b in codecs.iterencode(text, codec):
        yield i
        i += len(b)
    yield i

def iter_codepoint_indices_utf8(text):
    """
    Iterate over the byte offset of each character (UTF-8 only).
    """
    octets = text.encode('utf-8')
    for i, c in enumerate(octets):
        # Enumerate all bytes, but omit the continuation bytes (10xxxxxx).
        if not 0x80 <= c < 0xC0:
            yield i
    yield len(octets)

def iter_byte_indices(text, codec):
    """
    Iterate over the codepoint offset of each byte (any codec).
    """
    for i, b in enumerate(codecs.iterencode(text, codec)):
        for _ in b:
            yield i
    yield len(text)

def iter_byte_indices_utf8(text):
    """
    Iterate over the codepoint offset of each byte (UTF-8 only).
    """
    octets = text.encode('utf-8')
    i = -1
    for c in octets:
        if not 0x80 <= c < 0xC0:
            i += 1
        yield i
    yield i+1  # == len(text)
