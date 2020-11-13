"""
Iteration utilities.
"""


__author__ = "Lenz Furrer"


import json
import itertools as it
from collections import deque
from contextlib import contextmanager


def ngrams(iterable, n, pad_left=False, pad_right=False,
           left_pad_symbol=None, right_pad_symbol=None):
    """Iterate over n-tuples with optional padding."""
    window = deque(maxlen=n)
    for _ in range((n-1)*pad_left):
        window.append(left_pad_symbol)
    for item in iterable:
        window.append(item)
        if len(window) == n:
            yield tuple(window)
    for _ in range((n-1)*pad_right):
        window.append(right_pad_symbol)
        if len(window) == n:
            yield tuple(window)


def peek(iterable):
    """
    Get the first element, then restore the iterator.
    """
    iterator = iter(iterable)
    first = next(iterator)
    restored = it.chain([first], iterator)
    return first, restored


class CacheOneIter:
    """
    An iterator which provides a method for repeating the last item.
    """

    def __init__(self, iterable):
        self._base = iter(iterable)
        self._current = None
        self._proceed = True

    def __iter__(self):
        return self

    def __next__(self):
        if self._proceed:
            self._current = next(self._base)
        self._proceed = True
        return self._current

    def repeat(self):
        """
        In the next iteration, yield the same item again.

        If this is called before the first call to __next__,
        the first item will be None.
        """
        self._proceed = False


def json_iterencode(o, check_circular=False, indent=2, **kwargs):
    """
    Iterate over chunks of serialised JSON.

    Iterators are supported.
    """
    enc = json.JSONEncoder(check_circular=check_circular, indent=indent,
                           default=jsonable_iterator, **kwargs)
    return enc.iterencode(o)

def jsonable_iterator(o):
    """
    Default function for encoding iterators in JSON.

    Warning: Relies on some implementation details about how
    lists/tuples are serialised.
    """
    # For lists/tuples, the JSON encoder
    # (1) checks if the list is non-empty, and
    # (2) if so, iterates over the elements (once).
    #
    # This function wraps non-empty iterators in a _PhonyList,
    # which inherits from list in order to pass the isinstance()
    # test.  Besides that, its bool() value is True and it can
    # be iterated over (once).
    try:
        first = next(o)
    except AttributeError:
        raise TypeError("{!r} is not JSON serializable".format(o))
    except StopIteration:
        return ()
    else:
        return _PhonyList(it.chain([first], o))

class _PhonyList(list):
    """
    A wrapper for an iterator claiming to be a list.
    """
    def __init__(self, idata):
        super().__init__()
        self.idata = idata

    def __iter__(self):
        for elem in self.idata:
            yield elem

    def __bool__(self):
        return True


def context_coroutine(generator):
    """Wrap a coroutine in a context manager."""
    @contextmanager
    def _wrap(*args, **kwargs):
        cr = generator(*args, **kwargs)
        try:
            cr.send(None)
            yield cr
        finally:
            cr.close()
    return _wrap
