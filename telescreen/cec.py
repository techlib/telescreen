#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.task import LoopingCall
from twisted.internet import reactor
from twisted.python import log

#
# FIXME: Workaround for broken python3-libcec
#
#     https://bugzilla.redhat.com/show_bug.cgi?id=1394373
#
# There is some problem locating the _cec.so, which the following
# code fixes by inserting the proper directory into search path.
#
import sys
import os.path
from distutils.sysconfig import get_python_lib
sys.path.append(os.path.join(get_python_lib(1), 'cec'))

# Import libcec the usual way.
import cec


__all__ = ['CEC']


class CEC(object):
    """
    TV power control using HDMI sub-protocol CEC.
    """

    def __init__(self):
        self.status = 'unknown'
        self.devices = []

    def start(self):
        """
        Start periodic tasks, such as power status querying.
        """

        log.msg('Looking for CEC adapters...')
        if not self.connect():
            log.err('No CEC adapters found, aborting.')
            return

        log.msg('Detected CEC devices: {0!r}'.format(self.devices))

        log.msg('Starting CEC periodic tasks...')
        self.status_loop = LoopingCall(self.query_power_status)
        self.status_loop.start(15)

        log.msg('CEC started.')

    def connect(self):
        # Prepare configuration
        config = cec.libcec_configuration()
        config.strDeviceName = 'Telescreen'
        config.bActivateSource = 0
        config.clientVersion = cec.LIBCEC_VERSION_CURRENT
        config.deviceTypes.Add(cec.CEC_DEVICE_TYPE_TV)

        # Create client context
        self.lib = cec.ICECAdapter.Create(config)

        # Query adapters and use the first one we find.
        adapters = self.lib.DetectAdapters()

        if len(adapters) == 0:
            return False

        path = adapters[0].strComName

        log.msg('Opening CEC adapter {}...'.format(path))
        if not self.lib.Open(path):
            log.err('Failed to open CEC adapter {}, aborting.'.format(path))
            return False

        # Get a bit mask of active devices we can control.
        devices = lib.GetActiveDevices()

        self.devices = []
        for i in range(0, 15):
            if devices.IsSet(i):
                self.devices.append(i)

        return True

    def query_power_status(self):
        """
        Query power status of our device.
        """

        statuses = []

        for device in self.devices:
            status = lib.GetDevicePowerStatus(device)

            if status == cec.CEC_POWER_STATUS_ON:
                statuses.append('on')
            elif status == cec.CEC_POWER_STATUS_STANDBY:
                statuses.append('standby')
            elif status == cec.CEC_POWER_STATUS_TRANSITION_STANDBY_TO_ON:
                statuses.append('to-on')
            elif status == cec.CEC_POWER_STATUS_TRANSITION_ON_TO_STANDBY:
                statuses.append('to-standby')
            else:
                statuses.append('unknown')

        def and_status(a, b):
            if a == b:
                return a
            elif 'on' in (a, b) and 'to-on' in (a, b):
                return 'to-on'
            elif 'standby' in (a, b) and 'to-standby' in (a, b):
                return 'to-standby'
            else:
                return 'unknown'

        if not statuses:
            return 'on'

        self.status = reduce(and_status, statuses)

    def set_power_status(status):
        """
        Attempt to change the power status of all connected devices.

        Out of the known statuses only 'on' and 'standby' can be used here.
        """

        assert status in ('on', 'standby'), 'Invalid power status'

        if status == 'on':
            adapter.PowerOnDevices()
        elif status == 'standby':
            adapter.StandbyDevices()


# vim:set sw=4 ts=4 et:
