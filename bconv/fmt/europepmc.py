"""
Formatter for Europe PMC's JSON-lines format.
"""


__author__ = "Lenz Furrer"

__all__ = ['EuPMCFormatter', 'EuPMCZipFormatter']


import io
import json
import zipfile
import itertools as it

from ._export import StreamFormatter, ContinuousEntityFormatter


class EuPMCFormatter(StreamFormatter, ContinuousEntityFormatter):
    """
    Formatter for Europe PMC's named-entity annotation format.
    """

    ext = 'jsonl'

    def __init__(self, provider, src='MED', meta=('type', 'pref', 'uri'),
                 **kwargs):
        super().__init__(**kwargs)
        self.metadata = {'provider': provider, 'src': src}
        (self.type,
         self.pref,
         self.uri) = meta

    def write(self, content, stream):
        documents = content.units('document')
        self._write(documents, stream)

    def _write(self, documents, stream):
        for document in documents:
            doc = self._document(document, self.metadata)
            if doc['anns']:
                json.dump(doc, stream)
                stream.write('\n')

    def _document(self, document, meta):
        doc = dict(meta, id=document.id, anns=[])
        for s, sent in enumerate(document.units('sentence'), start=1):
            text = sent.text
            offset = sent.start
            section = self._section_name(sent.section, meta['src'])
            locations = it.groupby(self.iter_entities(sent),
                                   key=lambda e: (e.start-offset, e.end-offset))
            for l, ((start, end), colocated) in enumerate(locations, start=1):
                types = it.groupby(colocated, key=self._entity_type)
                for type_, entities in types:
                    entities = set(map(self._entity_name_uri, entities))
                    ann = {
                        'position': '{}.{}'.format(s, l),
                        'prefix': text[max(start-20, 0):start],
                        'postfix': text[end:end+20],
                        'exact': text[start:end],
                        'section': section,
                        'type': type_,
                        'tags': [{'name': n, 'uri': u} for n, u in entities]
                    }
                    doc['anns'].append(ann)
        return doc

    def _entity_type(self, entity):
        return self._entity_meta(entity, self.type)

    def _entity_name_uri(self, entity):
        return tuple(self._entity_meta(entity, k) for k in (self.pref, self.uri))

    @staticmethod
    def _entity_meta(entity, key):
        try:
            return entity.metadata[key]
        except KeyError as e:
            if e.args == (key,):
                raise ValueError(
                    'Need entity attribute: {!r} not found in Entity.metadata. '
                    'Please check the `meta` option.'
                    .format(key))
            raise

    def _section_name(self, section, src):
        name = section.type
        if src == 'PMC':
            if name not in self._pmc_sections:
                name = 'Article'
        elif name != 'Title':
            name = 'Abstract'
        return name

    _pmc_sections = frozenset((
        'Title', 'Abstract', 'Introduction', 'Methods', 'Results',
        'Discussion', 'Acknowledgments', 'References', 'Table', 'Figure',
        'Case study', 'Supplementary material', 'Conclusion', 'Abbreviations',
        'Competing Interests'))


class EuPMCZipFormatter(EuPMCFormatter):
    """
    Formatter for archives of Europe PMC's format.
    """

    ext = 'zip'
    binary = True

    def write(self, content, stream):
        documents = content.units('document')
        # Iterate in hunks of 10,000, the max number of lines per file allowed.
        hunks = it.groupby(documents, key=lambda _, i=it.count(): next(i)//10000)

        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as zf:
            for n, hunk in hunks:
                arcname = '{}_{}.jsonl'.format(
                    content.id or content.filename, n+1)
                try:
                    member = zf.open(arcname, mode='w')
                except RuntimeError:  # Python < 3.6 doesn't support mode='w'
                    member = io.BytesIO()
                with io.TextIOWrapper(member, encoding='utf8') as f:
                    self._write(hunk, f)
                    if isinstance(member, io.BytesIO):
                        zf.writestr(arcname, member.getvalue())
