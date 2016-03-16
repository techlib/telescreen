#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['message_schema']

from yaml import load
from os.path import dirname, join


with open(join(dirname(__file__), 'message-schema.yaml')) as fp:
    message_schema = load(fp)


# vim:set sw=4 ts=4 et:
