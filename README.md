# `bconv`: Python library for converting between BioNLP formats

`bconv` offers format conversion and manipulation of documents with text and annotations.
It supports various popular formats used in natural-language processing for biomedical texts.


## Supported formats

The following formats are currently supported:

| Name                               | I | O | T | A | Description |
| ---------------------------------- | - | - | - | - | ----------- |
| `bioc_xml`, `bioc_json`            | ✓ | ✓ | ✓ | ✓ | [BioC][1] |
| `bionlp`                           |   | ✓ |   | ✓ | [BioNLP stand-off][2] |
| `brat`                             |   | ✓ |   | ✓ | [brat stand-off][2] |
| `conll`                            | ✓ | ✓ | ✓ | ✓ | [CoNLL][3] |
| `europepmc`, `europepmc.zip`       |   | ✓ |   | ✓ | [Europe-PMC JSON][4] |
| `pubtator`, `pubtator_fbk`         | ✓ | ✓ | ✓ | ✓ | [PubTator][5] |
| `pubmed`, `pxml`                   | ✓ |   | ✓ |   | [PubMed abstracts][6] |
| `pmc`, `nxml`                      | ✓ |   | ✓ |   | [PMC full-text][6] |
| `pubanno_json`, `pubanno_json.tgz` | ✓ | ✓ | ✓ | ✓ | [PubAnnotation JSON][7] |
| `csv`, `tsv`                       |   | ✓ |   | ✓ | [comma/tab-separated values][8] |
| `text_csv`, `text_tsv`             |   | ✓ | ✓ | ✓ | [comma/tab-separated values][8] |
| `txt`                              | ✓ | ✓ | ✓ |   | [plain text][9] |
| `txt.json`                         | ✓ | ✓ | ✓ |   | [collection of plain-text documents][9] |

**I**: input format;
**O**: output format;
**T**: can represent text;
**A**: can represent annotations (entities).

[1]: https://github.com/lfurrer/bconv/wiki/BioC
[2]: https://github.com/lfurrer/bconv/wiki/Brat
[3]: https://github.com/lfurrer/bconv/wiki/CoNLL
[4]: https://github.com/lfurrer/bconv/wiki/EuropePMC
[5]: https://github.com/lfurrer/bconv/wiki/PubTator
[6]: https://github.com/lfurrer/bconv/wiki/PubMed
[7]: https://github.com/lfurrer/bconv/wiki/PubAnnotation
[8]: https://github.com/lfurrer/bconv/wiki/CSV
[9]: https://github.com/lfurrer/bconv/wiki/TXT


## Installation

`bconv` is hosted on [PyPI](https://pypi.org/project/bconv/), so you can use `pip` to install it:
```sh
$ pip install bconv
```


## Usage

Load an annotated collection in BioC XML format:
```pycon
>>> import bconv
>>> coll = bconv.load('path/to/example.xml', fmt='bioc_xml')
>>> coll
<Collection with 37 documents at 0x7f1966e4b3c8>
```
A Collection is a sequence of Document objects:
```pycon
>>> coll[0]
<Document with 12 sections at 0x7f1966e2f6d8>
```
Documents contain Sections, which contain Sentences:
```pycon
>>> sent = coll[0][3][5]
>>> sent.text
'A Live cell imaging reveals that expression of GFP‐KSHV‐TK, but not GFP induces contraction of HeLa cells.'
```
Find the first annotation for this sentence:
```pycon
>>> e = next(sent.iter_entities())
>>> e.start, e.end, e.text
(571, 578, 'KSHV‐TK')
>>> e.metadata
{'type': 'gene/protein', 'ui': 'Uniprot:F5HB62'}
```
Write the whole collection to a new file in CoNLL format:
```pycon
>>> with open('path/to/example.conll', 'w', encoding='utf8') as f:
...     bconv.dump(coll, f, fmt='conll', tagset='IOBES', include_offsets=True)
```


## Documentation

`bconv` is documented in the [GitHub wiki](https://github.com/lfurrer/bconv/wiki).
