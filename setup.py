#!/usr/bin/env python

import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.version_info < (3, 3):
    raise NotImplementedError("You need at least Python 3.3.")

import fossil

setup(
    name='fossilpy',
    version=fossil.__version__,
    description='Simple pure-python library for reading Fossil repositories.',
    long_description=open('README.rst', 'r').read(),
    author='Dingyuan Wang',
    author_email='gumblex@aosc.io',
    url='https://github.com/gumblex/fossilpy',
    py_modules=['fossil'],
    scripts=['fossil.py'],
    license='BSD',
    platforms='any',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Topic :: Software Development :: Version Control',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='fossil',
    extras_require={'checksum':  ["numpy"]}
)
