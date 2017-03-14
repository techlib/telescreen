#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

import os
import re

from time import time
from twisted.internet.task import LoopingCall
from twisted.python import log
from twisted.internet import reactor
from twisted.python.procutils import which
from twisted.internet.protocol import ProcessProtocol

from telescreen.common import Logging

__all__ = ['CEC']


CEC_POWER_STATUSES = {
    'on': 'on',
    'standby': 'standby',
    'in transition from standby to on': 'to-on',
    'in transition from on to standby': 'to-standby',
    'unknown': 'unknown',
}


class CECProtocol(ProcessProtocol, Logging):
    def __init__(self, recipient):
        self.recipient = recipient

    def connectionMade(self):
        pass

    def set_active_source(self):
        self.msg('Setting Telescreen as the active source...')
        self.transport.write('as 0\n'.encode('utf-8'))

    def set_power_status(self, status):
        self.msg('Setting power status to {!r}...'.format(status))
        self.transport.write('{} 0\n'.format(status).encode('utf-8'))

    def query_power_status(self):
        self.msg('Querying power status...')
        self.transport.write('pow 0\n'.encode('utf-8'))

    def outReceived(self, data):
        for line in data.decode('utf8').strip().split('\n'):
            self.lineReceived(line)

    def lineReceived(self, line):
        if 'power status:' in line:
            try:
                m = re.match('power status: (.*)', line)
                self.recipient.on_power_status(m.group(1).strip())
            except AttributeError:
                pass

    def processExited(self, reason):
        self.recipient.on_exit()

    def logPrefix(self):
        return 'cec'


class CEC(object):
    """
    TV power control using HDMI sub-protocol CEC.
    """

    def __init__(self):
        self.status = 'unknown'
        self.last_retry = time()
        self.protocol = CECProtocol(self)
        self.status_loop = None

    def start(self):
        args = ['cec-client', '-d', '1', '-t', 'p', '-o', 'Telescreen']
        reactor.spawnProcess(self.protocol, which('cec-client')[0], args)
        self.status_loop = LoopingCall(self.query_power_status)
        self.status_loop.start(15)

    def set_active_source(self):
        self.protocol.set_active_source()

    def set_power_status(self, status):
        self.protocol.set_power_status(status)

    def query_power_status(self):
        self.protocol.query_power_status()

    def on_power_status(self, status):
        prev_status = self.status
        self.status = CEC_POWER_STATUSES.get(status, 'unknown')

        if self.status != prev_status:
            log.msg('CEC power status changed: {!r}'.format(self.status))

    def on_exit(self):
        if (time() - self.last_retry) > 10:
            self.status_loop.stop()
            self.start()
            self.last_retry = time()
        else:
            log.msg('CEC process dying too often, exiting.')
            reactor.stop()

# vim:set sw=4 ts=4 et:
