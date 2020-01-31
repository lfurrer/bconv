#!/usr/bin/env python3
# coding: utf8

# Author: Nicola Colic, Lenz Furrer, 2018--2020


"""
Formatter for PubAnnotation JSON output.

http://www.pubannotation.org/docs/annotation-format/
"""


__all__ = ['PubAnnoJSONFormatter']


import json

from ._export import StreamFormatter


class PubAnnoJSONFormatter(StreamFormatter):
    """
    PubAnnotation JSON format.
    """

    ext = 'json'

    def __init__(self, cui='cui'):
        self.cui = cui

    def write(self, stream, content):
        json_object = {}
        json_object['text'] = content.text
        json_object['denotations'] = [self._entity(e)
                                      for e in content.iter_entities()]
        json.dump(json_object, stream)

    def _entity(self, entity):
        return {'id' : self._format_id(entity.id),
                'span' : {'begin': entity.start,
                          'end': entity.end},
                'obj' : entity.info[self.cui]}

    @staticmethod
    def _format_id(id_):
        """
        For numeric IDs, produce "T<N>" format.
        """
        if isinstance(id_, int) or id_.isdigit():
            return 'T{}'.format(id_)
        else:
            return id_
