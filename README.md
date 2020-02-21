# `bconv`: Python library for converting between BioNLP formats

`bconv` offers format conversion and manipulation of documents with text and annotations.
It supports various popular formats used in natural-language processing for biomedical texts.


## Supported formats

The following formats are currently supported:

| Name                         | I | O | T | A | Description |
| ---------------------------- | - | - | - | - | ----------- |
| `bioc_xml`, `bioc_json`      | ✓ | ✓ | ✓ | ✓ | BioC |
| `bionlp`                     |   | ✓ |   | ✓ | BioNLP stand-off |
| `brat`                       |   | ✓ |   | ✓ | brat stand-off |
| `conll`                      | ✓ | ✓ | ✓ | ✓ | CoNLL |
| `europepmc`, `europepmc.zip` |   | ✓ |   | ✓ | Europe-PMC JSON |
| `pubtator`, `pubtator_fbk`   | ✓ | ✓ | ✓ | ✓ | PubTator |
| `pubmed`, `pxml`, `pxml.gz`  | ✓ |   | ✓ |   | PubMed abstracts |
| `pmc`, `nxml`                | ✓ |   | ✓ |   | PMC full-text |
| `pubanno_json`               |   | ✓ | ✓ | ✓ | PubAnnotation JSON |
| `tsv`, `text_tsv`            |   | ✓ | ✓ | ✓ | tab-separated values |
| `txt`                        | ✓ | ✓ | ✓ |   | plain text |
| `txt_json`                   | ✓ |   | ✓ |   | collection of plain-text documents |

I: input format;
O: output format;
T: can represent text;
A: can represent annotations (entities).


## Installation

`bconv` is hosted on [PyPI](https://pypi.org/project/bconv/), so you can use `pip` to install it:
```sh
$ pip install bconv
```
By default, `pip` attempts a system-level installation, which might require admin privileges.
Alternatively, use `pip`'s `--user` flag for an installation owned by the current user.


## Usage

Load an annotated collection in BioC XML format:
```pycon
>>> import bconv
>>> coll = bconv.load('bioc_xml', 'path/to/example.xml')
>>> coll
<Collection with 37 subelements at 0x7f1966e4b3c8>
```
A Collection is a sequence of Document objects:
```pycon
>>> coll[0]
<Document with 12 subelements at 0x7f1966e2f6d8>
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
>>> e.info
{'type': 'gene/protein', 'ui': 'Uniprot:F5HB62'}
```
Write the whole collection to a new file in CoNLL format:
```pycon
>>> with open('path/to/example.conll', 'w', encoding='utf8') as f:
...     bconv.dump('conll', coll, f, tagset='IOBES', include_offsets=True)
```
