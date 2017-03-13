#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

import os
import re

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
    def __init__(self, callback=log.msg):
        self.callback = callback

    def connectionMade(self):
        pass

    def set_active_source(self):
        self.msg('Setting active source to 0...')
        self.transport.write('as 0\n'.encode('utf-8'))

    def set_power_status(self, status):
        self.msg('Setting power status to {!r}...'.format(status))
        self.transport.write('{} 0\n'.format(status).encode('utf-8'))

    def query_power_status(self):
        self.msg('Querying power status...')
        self.transport.write('pow 0\n'.encode('utf-8'))

    def outReceived(self, data):
        self.callback(data)

    def logPrefix(self):
        return 'cec'


class CEC(object):
    """
    TV power control using HDMI sub-protocol CEC.
    """

    def __init__(self):
        self.status = 'unknown'
        self.protocol = CECProtocol(callback=self._parse_power_status)

    def start(self):
        reactor.spawnProcess(self.protocol, which('cec-client')[0],
                             args=('cec-client', '-d', '1'))
        self.status_loop = LoopingCall(self.query_power_status)
        self.status_loop.start(15)

    def set_active_source(self):
        self.protocol.set_active_source()

    def set_power_status(self, status):
        self.protocol.set_power_status(status)

    def query_power_status(self):
        self.protocol.query_power_status()

    def _parse_power_status(self, data):
        try:
            m = re.match('power status: (.*)', data.strip().decode('utf-8'))
            self.status = CEC_POWER_STATUSES[m.group(1).strip()]
        except AttributeError:
            pass


# vim:set sw=4 ts=4 et:
