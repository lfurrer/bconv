"""
Word tokenisation and sentence splitting.
"""


__author__ = "Lenz Furrer"

__all__ = ['TOKENIZER']


from ..util.iterate import ngrams


class Tokenizer:
    """
    Lazy wrapper for token and sentence splitting.
    """

    def __init__(self):
        self._word_tokenizer = None
        self._sentence_splitter = None

    @property
    def word_tokenizer(self):
        """Tokenizer object with a `span_tokenize` method."""
        if self._word_tokenizer is None:
            from nltk.tokenize import WordPunctTokenizer
            self._word_tokenizer = WordPunctTokenizer()
        return self._word_tokenizer

    @word_tokenizer.setter
    def word_tokenizer(self, tokenizer):
        self._word_tokenizer = tokenizer

    @property
    def sentence_splitter(self):
        """Sentence-splitter object with a `span_tokenize` method."""
        if self._sentence_splitter is None:
            from nltk.tokenize import PunktSentenceTokenizer
            self._sentence_splitter = PunktSentenceTokenizer()
        return self._sentence_splitter

    @sentence_splitter.setter
    def sentence_splitter(self, tokenizer):
        self._sentence_splitter = tokenizer

    def split_sentences(self, text, offset=0):
        """Iterate over sentence triples <text, start, end>."""
        # Use a trick to get spans that always include trailing whitespace.
        # Iterate over bigrams of spans, ie.
        #   <start_n, end_n>, <start_n+1, end_n+1>
        # and then use <start_n, start_n+1> as the span for n.
        # To get the last sentence right, use padding.
        spans = self.sentence_splitter.span_tokenize(text)
        spans = ngrams(spans, 2, pad_right=True,
                       right_pad_symbol=(len(text), None))
        for (start, _), (end, _) in spans:
            yield text[start:end], start+offset, end+offset

    def tokenize(self, text, offset=0):
        """Iterate over token triples <text, start, end>."""
        for start, end in self.word_tokenizer.span_tokenize(text):
            yield text[start:end], start+offset, end+offset


# Global default instance.
TOKENIZER = Tokenizer()
