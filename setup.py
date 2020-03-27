#!/usr/bin/env python3
# coding: utf8

# Author: Lenz Furrer, 2020


import setuptools

import bconv


try:
    from m2r import parse_from_file
except ImportError:
    with open('README.md') as f:
        long_description = f.read()
    content_type = "text/markdown"
else:
    long_description = parse_from_file('README.md')
    content_type = "text/x-rst"


setuptools.setup(
    name='bconv',
    version=bconv.__version__,
    description="Convert between BioNLP formats",
    long_description=long_description,
    long_description_content_type=content_type,
    url='https://github.com/lfurrer/bconv',
    author='Lenz Furrer',
    author_email='lenz.furrer@gmail.com',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'lxml',
        'nltk',
    ],
)
