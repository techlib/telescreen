#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from os.path import *

def read_requires(path=None):
    if path is None:
        path = join(dirname(__file__), 'requirements.txt')
        print(path)

    with open(path) as fp:
        return [l.strip() for l in fp.readlines()]

setup(
    name = 'telescreen',
    version = '1',
    author = 'NTK',
    description = ('Digital signage player for GNOME'),
    license = 'MIT',
    keywords = 'video image slideshow indoktrinator',
    url = 'http://github.com/techlib/telescreen',
    include_package_data = True,
    packages = find_packages(),
    classifiers = [
        'License :: OSI Approved :: MIT License',
    ],
    scripts = ['bin/telescreen'],
    install_requires = read_requires(),
)


# vim:set sw=4 ts=4 et:
