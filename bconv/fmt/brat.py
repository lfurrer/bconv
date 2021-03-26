"""
Formatters for brat-like stand-off formats.
"""


__author__ = "Lenz Furrer"

__all__ = ['BratFormatter', 'BioNLPFormatter']


import re
from collections import defaultdict

from ._export import StreamFormatter, EntityFormatter
from ..util.iterate import pids


class _BaseBratFormatter(StreamFormatter, EntityFormatter):
    """
    Abstract base class for Brat and BioNLP formatting.
    """

    T_LINE = '{}\t{} {}\t{}\n'
    N_LINE = '{}\tReference {} {}\t{}\n'
    A_LINE = '{}\t{} {} {}\n'
    R_LINE = '{}\t{} {}\n'
    E_LINE = '{}\t{}\n'

    def __init__(self, att='type', **kwargs):
        super().__init__(**kwargs)
        self.att = att

    def write(self, content, stream):
        counters = [pids(prefix) for prefix in 'TNARE']
        for doc in content.units('document'):
            self._write_anno(stream, doc, counters)

    def _write_anno(self, stream, document, counters):
        """
        Write document-level annotations with continuous IDs.
        """
        c_t, c_n, c_a, c_r, c_e = counters
        entity_refs = dict(self._write_entities(stream, document, c_t, c_n, c_a))
        self._write_relations(stream, document, entity_refs, c_r, c_e)

    def _write_entities(self, stream, document, c_t, c_n, c_a):
        raise NotImplementedError

    def _write_relations(self, stream, document, entity_refs, c_r, c_e):
        relations = []
        for relation in document.iter_relations():
            if len(relation) == 2 and relation.type is not None:
                id_ = next(c_r)
                line = self.R_LINE.format(id_, relation.type, '{}')
            else:
                id_ = next(c_e)
                line = self.E_LINE.format(id_, '{}')
            entity_refs[relation.id] = id_
            relations.append((relation, line))
        for relation, line in relations:
            members = ' '.join('{}:{}'.format(m.role, entity_refs[m.refid])
                               for m in relation)
            stream.write(line.format(members))

    def _get_att(self, entity, key=None, option_name='att'):
        if key is None:
            key = self.att
        try:
            return entity.metadata[key]
        except KeyError as e:
            if e.args == (key,):
                raise ValueError(
                    'Need entity attribute: {!r} not found in Entity.metadata. '
                    'Please check the `{}` option.'
                    .format(key, option_name))
            raise

    @staticmethod
    def _format_offsets(entity):
        return ';'.join(' '.join(map(str, span)) for span in entity.spans)


class BratFormatter(_BaseBratFormatter):
    """
    Stand-off annotations for brat.

    Accompany each output file with a txt dump.
    """

    ext = 'ann'
    _fieldname_pattern = re.compile(r'\W+')

    def __init__(self, att='type', cui=None, extra=()):
        """
        Args:
            att: metadata key of the attribute value
                 (used in the "type" slot of a T line)
            cui: metadata key of the concept ID
                 (used in a separate N line)
            extra: metadata keys for additional attributes
                   (used in a separate A line)
        """
        super().__init__(att=att)
        self.cui = cui
        self.extra = extra

    def _write_entities(self, stream, document, c_t, c_n, c_a):
        mentions = self._get_mentions(document)
        for (loc_att, entities), t in zip(sorted(mentions.items()), c_t):
            stream.write(self.T_LINE.format(t, *loc_att[2:]))
            for e in entities:
                # Add concept IDs (normalisation/linking) if specified.
                self._write_normalisation(stream, e, t, c_n)
                # Add all remaining information as attribute annotations.
                self._write_attributes(stream, e, t, c_a)
                # Keep track of the entity counter for references in relations.
                yield e.id, t

    def _write_normalisation(self, stream, entity, t, c_n):
        if self.cui is not None:
            value = self._get_att(entity, self.cui, 'cui')
            stream.write(self.N_LINE.format(next(c_n), t, value, entity.text_wn))

    def _write_attributes(self, stream, entity, t, c_a):
        for key, a in zip(self.extra, c_a):
            value = self._get_att(entity, key, 'extra')
            stream.write(self.A_LINE.format(a, key, t, value))

    def _get_mentions(self, document):
        mentions = defaultdict(list)
        for e in self.iter_entities(document):
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

    def _write_entities(self, stream, document, c_t, *_):
        for entity, t in zip(self.iter_entities(document), c_t):
            att = self._get_att(entity)
            offsets = self._format_offsets(entity)
            stream.write(self.T_LINE.format(t, att, offsets, entity.text_wn))
            # Keep track of the entity counter for references in relations.
            yield entity.id, t
