#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['get_power_status', 'set_power_status']

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


def get_power_status():
    """
    Determine aggregate power status of all connected devices.

    Valid power statuses are 'on', 'standby', 'to-on', 'to-standby',
    and 'unknown'.

    - When all devices agree on a status, returns that status.

    - When device statuses disagree, returns 'unknown'.

    - When some devices are transitioning and some have already reached
      the target status, returns 'to-on' or 'to-standby' respectively.

    - When there are not devices, returns 'on'.
    """

    statuses = []

    for adapter in cec.AdapterVector():
        for device in adapter.GetActiveDevices():
            status = adapter.GetDevicePowerStatus(device)

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

    return reduce(and_status, statuses)


def set_power_status(status):
    """
    Attempt to change the power status of all connected devices.

    Out of the known statuses only 'on' and 'standby' can be used here.
    """

    assert status in ('on', 'standby'), 'Invalid power status'

    for adapter in cec.AdapterVector():
        for device in adapter.GetActiveDevices():
            if status == 'on':
                adapter.PowerOnDevices(device)
            elif status == 'standby':
                adapter.StandbyDevices(device)


# vim:set sw=4 ts=4 et:
