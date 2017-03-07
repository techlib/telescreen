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
from functools import reduce
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
        #self.devices = []

    def start(self):
        """
        Start periodic tasks, such as power status querying.
        """

        log.msg('Looking for CEC adapters...')
        if not self.connect():
            log.msg('No CEC adapters found, aborting.')
            return

        #log.msg('Detected CEC devices: {0!r}'.format(self.devices))

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
            log.msg('Failed to open CEC adapter {}, aborting.'.format(path))
            return False

        return True

    def close(self):
        self.lib.Close()

    def query_power_status(self):
        """
        Query power status of our device.
        """

        status = self.lib.GetDevicePowerStatus(cec.CEC_DEVICE_TYPE_TV)

        if status == cec.CEC_POWER_STATUS_ON:
            return 'on'
        elif status == cec.CEC_POWER_STATUS_STANDBY:
            return 'standby'
        elif status == cec.CEC_POWER_STATUS_IN_TRANSITION_STANDBY_TO_ON:
            return 'to-on'
        elif status == cec.CEC_POWER_STATUS_IN_TRANSITION_ON_TO_STANDBY:
            return 'to-standby'
        else:
            return 'unknown'

    def set_power_status(self, status):
        """
        Attempt to change the power status of the TV.

        Out of the known statuses only 'on' and 'standby' can be used here.
        """
        assert status in ('on', 'standby'), 'Invalid power status'

        if status == 'on':
            self.lib.PowerOnDevices(cec.CEC_DEVICE_TYPE_TV)
        elif status == 'standby':
            self.lib.StandbyDevices(cec.CEC_DEVICE_TYPE_TV)


# vim:set sw=4 ts=4 et:
