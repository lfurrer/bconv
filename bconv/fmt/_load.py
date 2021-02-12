"""
Loader base classes.
"""


__author__ = "Lenz Furrer"


from ..doc.document import Collection
from ..util.stream import basename


class Loader:
    """
    Abstract base loader.

    Subclasses must implement load_one().
    """

    def load_one(self, source, id):
        """
        Load a single content (Document or Collection).
        """
        raise NotImplementedError()


class DocLoader(Loader):
    """
    Load a single document at a time.

    Subclasses must implement document().
    """

    def load_one(self, source, id):
        return self.document(source, id)

    def document(self, source, id):
        """
        Load a single document.
        """
        raise NotImplementedError()


class CollLoader(Loader):
    """
    Load a whole collection of documents.

    Subclasses must implement collection().
    """

    def load_one(self, source, id):
        return self.collection(source, id)

    def collection(self, source, id):
        """
        Load a complete collection.
        """
        raise NotImplementedError()

    def iter_documents(self, source):
        """
        Iterate over the documents of a collection.
        """
        yield from self.collection(source, id=None)


class DocIterator(Loader):
    """
    Load multiple documents from a single source.

    Subclasses must implement iter_documents().
    """

    def load_one(self, source, id):
        docs = self.iter_documents(source)
        return Collection.from_iterable(docs, id, basename(source))

    def iter_documents(self, source):
        """
        Iterate over all documents.
        """
        raise NotImplementedError()


def wrap_in_collection(content):
    """
    If this is a document, wrap it in a collection.
    """
    if not isinstance(content, Collection):
        coll = Collection(content.id, content.filename)
        coll.add_document(content)
        content = coll
    return content


def text_node(tree_or_elem, xpath, onerror=None, ifnone=None):
    """
    Get the text node of the referenced element.

    If the node cannot be found, return `onerror`:
    If the node is found, but its text content is None,
    return ifnone.
    """
    try:
        text = tree_or_elem.find(xpath).text
    except AttributeError:
        text = onerror
    else:
        if text is None:
            text = ifnone
    return text
