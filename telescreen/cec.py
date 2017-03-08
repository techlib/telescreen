#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

import os
import re

from twisted.internet.task import LoopingCall
from twisted.python import log
from twisted.internet import reactor
from twisted.python.procutils import which
from twisted.internet.protocol import ProcessProtocol


__all__ = ['CEC']


CEC_POWER_STATUSES = {
    'on': 'on',
    'standby': 'standby',
    'in transition from standby to on': 'to-on',
    'in transition from on to standby': 'to-standby',
    'unknown': 'unknown',
}


class CECProtocol(ProcessProtocol):
    def __init__(self, command, callback=log.msg):
        self.command = command
        self.callback = callback

    def connectionMade(self):
        self.transport.write(self.command.encode('utf-8'))
        self.transport.closeStdin()

    def outReceived(self, data):
        self.callback(data)


class CEC(object):
    """
    TV power control using HDMI sub-protocol CEC.
    """

    def __init__(self):
        self.status = 'unknown'

    def start(self):
        self.status_loop = LoopingCall(self.query_power_status)
        self.status_loop.start(15)

    def set_power_status(self, status):
        protocol = CECProtocol('{} 0'.format(status))
        reactor.spawnProcess(protocol, which('cec-client')[0],
                             args=['cec-client', '-s', '-d', '1'])

    def query_power_status(self):
        protocol = CECProtocol('pow 0', self._parse_power_status)
        reactor.spawnProcess(protocol, which('cec-client')[0],
                             args=['cec-client', '-s', '-d', '1'])

    def _parse_power_status(self, data):
        try:
            m = re.match('power status: (.*)', data.decode('utf-8'))
            self.status = CEC_POWER_STATUSES[m.group(1)]
        except AttributeError:
            pass


# vim:set sw=4 ts=4 et:
