"""
Formatter for PubAnnotation JSON output.

http://www.pubannotation.org/docs/annotation-format/
"""


__author__ = "Nicola Colic, Lenz Furrer"

__all__ = ['PubAnnoJSONFormatter', 'PubAnnoTGZFormatter']


import io
import json
import time
import tarfile

from ._export import Formatter, StreamFormatter
from ..doc.document import Collection, Document, Section


class PubAnnoJSONFormatter(Formatter):
    """
    PubAnnotation JSON format.
    """

    ext = 'json'

    def __init__(self, obj='cui', sourcedb=None, **meta):
        self.obj = obj
        self.meta = {'sourcedb': sourcedb, **meta}

    def write(self, content, stream):
        json.dump(self._prepare(content), stream, indent=2)

    def dumps(self, content):
        return json.dumps(self._prepare(content), indent=2)

    def _prepare(self, content):
        if isinstance(content, Section):
            json_object = self._division(content)
        elif isinstance(content, Document):
            json_object = self._document(content)
        elif isinstance(content, Collection):
            json_object = [self._document(doc) for doc in content]
        else:
            raise ValueError('Cannot serialise {}'.format(type(content)))
        return json_object

    def _division(self, section, divid=1):
        return self._annotation(section, offset=section.start,
                                sourceid=section.document.id, divid=divid)

    def _document(self, document):
        return self._annotation(document, sourceid=document.id)

    def _annotation(self, content, offset=0, **meta):
        return {
            'text': content.text,
            'denotations': list(self._entities(content, offset)),
            **meta,
            **self.meta,
        }

    def _entities(self, content, offset):
        for id_, entity in enumerate(content.iter_entities(), start=1):
            yield {
                'id' : 'T{}'.format(id_),
                'span' : {'begin': entity.start-offset,
                          'end': entity.end-offset},
                'obj' : entity.info[self.obj]
            }


class PubAnnoTGZFormatter(StreamFormatter, PubAnnoJSONFormatter):
    """
    Gzipped TAR archive with PubAnnotation JSON files.
    """

    ext = 'tgz'
    binary = True

    def write(self, content, stream):
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            for doc in content.units(Document):
                for divid, sec in enumerate(doc, start=1):
                    div = self._division(sec, divid=divid)
                    name = '{}-{}.json'.format(div['sourceid'], divid)
                    blob = json.dumps(div, indent=2).encode('utf8')
                    info = tarfile.TarInfo(name)
                    info.size = len(blob)
                    info.mtime = time.time()
                    tar.addfile(info, io.BytesIO(blob))
