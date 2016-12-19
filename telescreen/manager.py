#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager', 'seconds_since_midnight']


from twisted.internet.task import LoopingCall
from twisted.internet.error import AlreadyCalled
from twisted.internet import reactor
from twisted.python import log

from datetime import datetime
from jsonschema import validate, ValidationError
from telescreen.screen import VideoItem, ImageItem, AudioVideoItem
from subprocess import Popen, PIPE
import time

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


class Manager(object):
    '''
    Global object holder
    '''
    def __init__(self, screen, machine, check_interval):
        self.client = None
        self.screen = screen
        self.planner = Planner(screen)
        self.machine = machine
        self.check_interval = check_interval
        self.power = False

        self.screen.manager = self
        self.planner.manager = self

    def start(self):
        log.msg('Manager started.')
        self.client.init()

    def poweron(self, force=False):
        """Wake up all connected devices."""

        if self.power is False or force:
            log.msg('Power TV ON')
            self.power = True

            for adapter in cec.AdapterVector():
                for device in adapter.GetActiveDevices():
                    adapter.PowerOnDevices(device)

    def poweroff(self, force=False):
        """Standby all connected devices."""

        if self.power or force:
            log.msg('Power TV OFF')
            self.power = False

            for adapter in cec.AdapterVector():
                for device in adapter.GetActiveDevices():
                    adapter.StandbyDevices(device)


class Planner(object):
    '''
    object tht plan event
    '''
    def __init__(self, screen):
        '''
        Inicialize variable
        '''
        self.screen = screen
        self.schedule = set()
        self.items = []
        self.events = []

        self.end = None
        self.poweroff = None
        self.playing_items = []

    def change_plan(self, plan):
        '''
        if is plan changed
        '''
        for event in self.events:
            try:
                event.cancel()
            except AlreadyCalled:
                pass

        for item in self.schedule:
            try:
                if item not in self.playing_items:
                    self.screen.stage.remove_child(item.actor)
            except:
                log.err()

        self.schedule = set()
        self.events = []
        self.items = plan

        self.next()

    def _next(self):
        '''
        Get next item to play
        '''
        now = seconds_since_midnight()
        while self.items:
            data = self.items[0]
            self.items = self.items[1:]

            if data['start'] >= now:
                return data

    def next(self):
        '''
        Schedule next item to play
        '''
        now = seconds_since_midnight()
        data = self._next()
        item = None
        self.end = self.end or now

        # reset power off
        if self.poweroff is not None:
            self.poweroff.cancel()
            self.poweroff = None

        # if there are some data
        if data is not None:
            # skipp item after interval
            if data['end'] < now:
                return self.next()

            # plan video
            if data['type'] == 'video':
                item = VideoItem(self, data['uri'])

            # plan image
            elif data['type'] == 'image':
                item = ImageItem(self, data['uri'])

            elif data['type'] == 'audiovideo':
                item = AudioVideoItem(self, data['uri'])

            # other plan
            else:
                log.msg('Unknown item type {0!r}'.format(data['type']))

        # if there is item to plan
        if item is not None:
            self.end = data['end']
            self.schedule_item(item, data['start'], data['end'])

        # if there is not item to play
        # we can poweroff TV
        else:
            self.poweroff = reactor.callLater(self.end, self.manager.poweroff)

    def schedule_item(self, item, start, end):
        '''
        Add callback to internal loop and register future object
        '''
        self.schedule.add(item)
        self.screen.stage.add_child(item.actor)

        now = seconds_since_midnight()
        play_in = max(start - now, 0)
        stop_in = max(end - now, 0)

        log.msg('Schedule {0!r} in {1!r}s.'.format(item.uri, play_in))

        self.events.append(reactor.callLater(play_in, item.play))
        self.events.append(reactor.callLater(stop_in, item.stop))

    def playing(self, item):
        '''
        set playing indicator and show item
        '''
        log.msg('Item %r playing.' % item.uri)
        item.appear()

    def paused(self, item):
        '''
        set paused indicator
        '''
        log.msg('Item %r paused.' % item.uri)

    def stopped(self, item):
        '''
        set stop indicator and hide item
        '''
        log.msg('Item %r stopped.' % item.uri)

    def appeared(self, item):
        '''
        set appered indicator
        '''
        log.msg('Item %r appeared.' % item.uri)

    def disappeared(self, item):
        '''
        set disappeared indicator and remove item
        '''
        log.msg('Item %r disappeared.' % item.uri)
        self.screen.stage.remove_child(item.actor)


def seconds_since_midnight():
    '''
    Calc actual number of seconds from midnight
    '''
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (now - midnight).total_seconds()


# vim:set sw=4 ts=4 et:
