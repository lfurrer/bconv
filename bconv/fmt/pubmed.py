"""
Loaders for different formats provided by PubMed.
"""


__author__ = "Lenz Furrer"

__all__ = ['PXMLLoader', 'PXMLFetcher', 'PMCLoader', 'PMCFetcher']


import os
import logging
import urllib.parse
import urllib.request
import itertools as it

from lxml import etree

from ._load import DocIterator, text_node
from ..doc.document import Document, Entity
from ..nlp.tokenize import TOKENIZER


class _MedlineParser:
    """
    Mixin for parsing PubMed abstracts in Medline's XML format.
    """

    tag = ('MedlineCitation', 'BookDocument')

    def __init__(self, single_section=False,
                 include_mesh=False, mesh_as_entities=False):
        super().__init__()
        self.single_section = single_section
        self.include_mesh = include_mesh
        self.mesh_as_entities = mesh_as_entities

    def _document(self, node, docid):
        # Get the PMID, if missing.
        if docid is None:
            docid = text_node(node, './/PMID')

        doc = Document(docid)
        # Add metadata if they can be found.
        doc.metadata = dict(self._get_metadata(node))

        # Title.
        title = node.find('.//ArticleTitle')
        if title is not None:  # title may be missing for BookDocument
            doc.add_section('Title', ''.join(title.itertext()) + '\n')

        # Abstract body might contain multiple sections, incl. a MeSH list.
        sections = self._iter_sections(node)

        if self.single_section:
            sections = self._conflate_sections(sections)

        anno_counter = it.count(1)
        for label, text, anno in sections:
            doc.add_section(label, text)
            if any(anno):
                self._insert_annotations(doc[-1], anno, anno_counter)

        return doc

    @staticmethod
    def _get_metadata(root):
        date = root.find('.//DateCompleted')  # MedlineCitation
        if date is not None:
            yield 'date', '-'.join(date.find(x).text
                                   for x in ('.//Year', './/Month', './/Day'))
        else:
            date = root.find('.//PubDate')  # BookDocument
            if date is not None:
                # PubDate can be year-month(-day), year-season, or free text.
                yield 'date', '-'.join(elem.text for elem in date)

        # There may be multiple publication types -- the first one is enough.
        type_ = text_node(root, './/PublicationType')
        if type_:
            yield 'type', type_

    def _iter_sections(self, root):
        placeholder = [None]
        for section in root.iterfind('.//AbstractText'):
            # Sectioned abstracts have a label attribute.
            # Otherwise, use the containing elem's tag as the label
            # (usually "Abstract").
            text = ''.join(section.itertext())
            if not text:
                continue
            label = section.get('Label')
            if label is None:
                label = section.getparent().tag
            yield label, text + '\n', placeholder

        # Optionally add the MeSH list.
        add_anno = self.mesh_as_entities
        if add_anno or self.include_mesh:
            mesh = [(entry.text + '\n', entry.get('UI', 'unknown'))
                    for entry in root.iterfind('.//MeshHeading/DescriptorName')
                    if entry.text]
            if mesh:
                names, uis = zip(*mesh)
                if not add_anno:
                    uis = [None for _ in uis]
                yield 'MeSH descriptor names', names, uis

    @staticmethod
    def _conflate_sections(sections):
        """
        Conflate the sections into one.

        Put the section headers into the text (unless it is "UNLABELLED").
        Append separators to each element.
        """
        # Temporary container for sentences, offsets and (optional) MeSH IDs.
        flat = []  # type: List[Tuple[str, Optional[str]]]
        for label, text, anno in sections:
            if label not in ('UNLABELLED', 'Abstract'):
                flat.append((label + ': ', None))
            if isinstance(text, str):
                sents = TOKENIZER.tokenize_sentences(text)
                flat.extend((sent, None) for sent in sents)
            else:
                # List of MeSH headings.
                flat.extend(zip(text, anno))
        text, anno = zip(*flat) if flat else ((), ())
        yield 'Abstract', text, anno

    @staticmethod
    def _insert_annotations(section, uis, counter):
        # Annotations come from the MeSH heading lists.
        # They are annotated at document level, but we need character
        # offsets, so the names are included as text in a separate section
        # in order to serve as an anchor for the Entity objects.
        # Each descriptor name is included as a separate sentence.

        # When constructing the Document object, an ID is recorded for every
        # piece of text. It is a placeholder (None) most of the time.
        # This allows dealing with the complexity introduced with the
        # single-section option, which affects the offsets (among other things).

        for sent, ui in zip(section, uis):
            if ui is None:
                continue
            id_ = next(counter)
            text = sent.text.rstrip()
            start = sent.start
            end = start + len(text)
            info = {'ui': ui, 'source': 'MeSH'}
            sent.add_entities((Entity(id_, text, start, end, info),))


class _PMCParser:
    """
    Mixin for parsing PubMed Central's full-text XML.
    """

    tag = 'article'
    NL = '\n\n'

    def _document(self, node, docid):
        title = self._get_title(node)
        abstract = self._sentence_split(self._get_abstract(node))
        if docid is None:
            docid = self._get_docid(node)

        doc = Document(docid)
        doc.add_section('title', title)
        doc.add_section('abstract', abstract)
        for type_, paragraphs in self._get_sections(node):
            doc.add_section(type_, self._sentence_split(paragraphs))

        return doc

    @staticmethod
    def _get_docid(node):
        """Try to get a missing ID, preferring PMCID and PMID."""
        for t in ('="pmc"', '="pubmed"', ''):
            n = node.find('.//article-id[@pub-id-type{}]'.format(t))
            if n is not None:
                return n.text
        return 'unknown'

    def _get_title(self, node):
        title = node.find('.//title-group/article-title')
        if title is None:
            title = node.find('.//article-categories/subj-group/subject')
        return self._itertext(title)

    def _get_abstract(self, root):
        for node in root.xpath('.//abstract'):
            if node.get("abstract-type"):
                yield node.get("abstract-type").capitalize() + self.NL
            else:
                yield "Abstract" + self.NL

            for abstract_section in node.xpath('.//title | .//p'):
                yield self._itertext(abstract_section)

    def _get_sections(self, root):
        for node in root.xpath('.//body'):
            paragraphs = node.iter('title', 'p', 'label')
            for sec, pnodes in it.groupby(paragraphs, key=self._top_level_sec):
                type_ = 'body' if sec is None else sec.get('sec-type', 'section')
                yield type_, map(self._itertext, pnodes)

    @staticmethod
    def _top_level_sec(node):
        sec = None
        for anc in node.iterancestors('sec', 'body'):
            if anc.tag == 'body':
                break  # don't go beyond this point
            sec = anc
        return sec

    @staticmethod
    def _sentence_split(texts):
        for text in texts:
            yield from TOKENIZER.tokenize_sentences(text)

    def _itertext(self, node):
        return ''.join(node.itertext()).strip() + self.NL


class _IterparseLoader(DocIterator):
    """
    Lazy loader for single- or multi-doc XML.

    Subclasses must override the "tag" class attribute.
    """

    tag = None  # type: str

    def iter_documents(self, source):
        if isinstance(source, os.PathLike):
            source = str(source)
        for _, node in etree.iterparse(source, tag=self.tag):
            yield self._document(node, None)
            node.clear()  # free memory

    def _document(self, node, docid):
        raise NotImplementedError()


class _NCBIFetcher(_IterparseLoader):
    """
    Fetch documents from NCBI's efetch interface.

    Subclasses must override the "db" class attribute.
    """

    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    db = None  # type: str

    def __init__(self, *args, tool='bconv', email=None, api_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = {
            k: v
            for k, v in [('tool', tool), ('email', email), ('api_key', api_key)]
            if v is not None}

    def load_one(self, source, id_):
        # Filename makes no sense for a fetched collection -- delete it.
        coll = super().load_one(source, id_)
        coll.filename = None
        return coll

    def iter_documents(self, source):
        """
        Iterate over documents from NCBI.
        """
        docids = source if isinstance(source, str) else ','.join(source)
        if not docids:
            raise ValueError('Empty document-ID list.')
        query = urllib.parse.urlencode(
            dict(db=self.db, retmode='xml', id=docids, **self.policy))
        logging.info(
            "POST request to NCBI's efetch API with the query %r", query)
        req = urllib.request.Request(self.url, data=query.encode('ascii'))

        with urllib.request.urlopen(req) as f:
            yield from super().iter_documents(f)


class PXMLLoader(_MedlineParser, _IterparseLoader):
    """
    Lazy loader for Medline XML (pxml).
    """


class PMCLoader(_PMCParser, _IterparseLoader):
    """
    Lazy loader for PMC full-text XML (nxml).
    """


class PXMLFetcher(_MedlineParser, _NCBIFetcher):
    """
    Loader for PubMed abstracts through efetch.
    """

    db = 'pubmed'


class PMCFetcher(_PMCParser, _NCBIFetcher):
    """
    Loader for PMC full-text documents through efetch.
    """

    db = 'pmc'
