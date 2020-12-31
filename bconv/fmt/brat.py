"""
Formatters for brat-like stand-off formats.
"""


__author__ = "Lenz Furrer"

__all__ = ['BratFormatter', 'BioNLPFormatter']


import re
import itertools as it
from collections import defaultdict

from ._export import StreamFormatter


class _BaseBratFormatter(StreamFormatter):
    """
    Abstract base class for Brat and BioNLP formatting.
    """

    T_LINE = 'T{}\t{} {}\t{}\n'
    A_LINE = 'A{}\t{} T{} {}\n'
    E_LINE = 'E{}\t{}\n'
    R_LINE = 'R{}\t{} {}\n'

    def __init__(self, att='type'):
        super().__init__()
        self.att = att

    def write(self, content, stream):
        counters = [it.count(1) for _ in range(3)]
        for doc in content.units('document'):
            self._write_anno(stream, doc, counters)

    def _write_anno(self, stream, document, counters):
        """
        Write document-level annotations with continuous IDs.
        """
        c_t, c_a, c_r = counters
        entity_refs = dict(self._write_entities(stream, document, c_t, c_a))
        self._write_relations(stream, document, entity_refs, c_r)

    def _write_entities(self, stream, document, c_t, c_a):
        raise NotImplementedError

    def _write_relations(self, stream, document, entity_refs, counter):
        relations = []
        for relation, r in zip(document.iter_relations(), counter):
            if len(relation) == 2 and relation.type is not None:
                id_ = 'R{}'.format(r)
                line = self.R_LINE.format(r, relation.type, '{}')
            else:
                id_ = 'E{}'.format(r)
                line = self.E_LINE.format(r, '{}')
            entity_refs[relation.id] = id_
            relations.append((relation, line))
        for relation, line in relations:
            members = ' '.join('{}:{}'.format(m.role, entity_refs[m.refid])
                               for m in relation)
            stream.write(line.format(members))

    def _get_att(self, entity, key=None):
        if key is None:
            key = self.att
        try:
            return entity.info[key]
        except KeyError as e:
            if e.args == (key,):
                raise ValueError(
                    'Need entity attribute: {!r} not found in Entity.info. '
                    'Please check the `{}` option.'
                    .format(key, 'att' if key == self.att else 'extra'))
            raise

    @staticmethod
    def _format_offsets(entity):
        return ';'.join(' '.join(map(str, span)) for span in entity.offsets)


class BratFormatter(_BaseBratFormatter):
    """
    Stand-off annotations for brat.

    Accompany each output file with a txt dump.
    """

    ext = 'ann'
    _fieldname_pattern = re.compile(r'\W+')

    def __init__(self, att='type', extra=()):
        """
        Args:
            att: info key of the attribute value
                 (used in the "type" slot of a T line)
            extra: info keys for additional attributes
                   (used in a separate A line)
        """
        super().__init__(att=att)
        self.extra = extra

    def _write_entities(self, stream, document, c_t, c_a):
        mentions = self._get_mentions(document)
        for (loc_att, entities), t in zip(sorted(mentions.items()), c_t):
            stream.write(self.T_LINE.format(t, *loc_att[2:]))
            for e in entities:
                # Add all remaining information as attribute annotations.
                self._write_attributes(stream, e, t, c_a)
                # Keep track of the entity counter for references in relations.
                yield e.id, 'T{}'.format(t)

    def _write_attributes(self, stream, entity, t, c_a):
        for key, a in zip(self.extra, c_a):
            value = self._get_att(entity, key)
            stream.write(self.A_LINE.format(a, key, t, value))

    def _get_mentions(self, document):
        mentions = defaultdict(list)
        for e in document.iter_entities():
            att = self._valid_fieldname(self._get_att(e))
            offsets = self._format_offsets(e)
            # Include start and end offset for sorting.
            mentions[e.start, e.end, att, offsets, e.text_wn].append(e)
        return mentions

    @classmethod
    def _valid_fieldname(cls, name):
        return cls._fieldname_pattern.sub('_', name)


class BioNLPFormatter(_BaseBratFormatter):
    """
    Stand-off annotations for BioNLP.

    Accompany each output file with a txt dump.

    Differences to the Brat format:
    - co-located annotations are not lumped together
    - att value is not sanitised
    - no extra attributes supported
    """

    ext = 'bionlp'

    def _write_entities(self, stream, document, c_t, _):
        for entity, t in zip(document.iter_entities(), c_t):
            att = self._get_att(entity)
            offsets = self._format_offsets(entity)
            stream.write(self.T_LINE.format(t, att, offsets, entity.text_wn))
            # Keep track of the entity counter for references in relations.
            yield entity.id, 'T{}'.format(t)
