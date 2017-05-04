#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.protocol import ProcessProtocol
from twisted.internet import reactor
from twisted.python import log

from telescreen import common

import sys
import os


__all__ = []


class DecoderClient (ProcessProtocol):
    def __init__(self, xid, media, url):
        args = [
            sys.argv[0],
            '--debug' if common.debug else '--quiet',
            '--decode', str(xid), media, url,
        ]
        reactor.spawnProcess(self, sys.argv[0], args, os.environ)

    def errReceived(self, data):
        if b'libva info:' not in data:
            sys.stderr.write(data)

    def outReceived(self, data):
        for event in data.decode('utf8').strip().split('\n'):
            getattr(self, 'on_{}'.format(event))()

    def prepare(self):
        self.transport.write(b'prepare\n')

    def play(self):
        self.transport.write(b'play\n')

    def stop(self):
        self.transport.write(b'stop\n')
        reactor.callLater(5, self.transport.loseConnection)

    def on_ready(self):
        pass

    def on_prepared(self):
        pass

    def on_playing(self):
        pass

    def processEnded(self, status):
        pass

    def connectionMade(self):
        pass


# vim:set sw=4 ts=4 et:
