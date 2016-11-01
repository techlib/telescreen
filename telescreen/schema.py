#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['schema']

from yaml import load
from os.path import dirname, join


with open(join(dirname(__file__), 'message-schema.yaml')) as fp:
    schema = load(fp)


# vim:set sw=4 ts=4 et:
