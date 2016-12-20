#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from yaml import load
from os.path import dirname, join


__all__ = ['schema']


with open(join(dirname(__file__), 'schema.yaml')) as fp:
    schema = load(fp)


# vim:set sw=4 ts=4 et:
