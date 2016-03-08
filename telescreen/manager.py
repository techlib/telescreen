#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.python import log

class Manager(object):
    def __init__(self, router, screen):
        self.router = router
        self.screen = screen

    def list_programs(self):
        return []

    def change_program(self, program):
        pass

    def start(self):
        log.msg('Manager started.')

# vim:set sw=4 ts=4 et:
