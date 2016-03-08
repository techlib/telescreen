#!/usr/bin/python3 -tt

from setuptools import setup, find_packages
import os.path

setup(
    name = 'telescreen',
    version = '1',
    author = 'NTK',
    description = ('info-screen presenter application'),
    license = 'MIT',
    keywords = 'video image slideshow',
    url = 'http://github.com/techlib/telescreen',
    include_package_data = True,
    packages = find_packages(),
    classifiers = [
        'License :: OSI Approved :: MIT License',
    ],
    scripts = ['bin/telescreen'],
)


# vim:set sw=4 ts=4 et:
# -*- coding: utf-8 -*-
