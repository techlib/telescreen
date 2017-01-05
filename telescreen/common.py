#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.python import log


__all__ = ['Logging']


class Logging:
    def log_prefix(self):
        return '-'

    def msg(self, text, **kw):
        return log.msg(text, system=self.log_prefix(), **kw)

    def err(self, *args, **kw):
        return log.err(*args, system=self.log_prefix(), **kw)


# vim:set sw=4 ts=4 et:
