# `bconv`: Python library for converting between BioNLP formats

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
