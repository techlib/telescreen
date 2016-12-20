#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.task import LoopingCall
from twisted.internet.error import AlreadyCalled
from twisted.internet import reactor
from twisted.python import log

from functools import *
from datetime import datetime
from jsonschema import validate, ValidationError
from uuid import uuid4

from telescreen.schema import message_schema
from telescreen.screen import VideoItem, ImageItem, AudioVideoItem
from telescreen.cec import get_power_status, set_power_status


__all__ = ['Manager', 'seconds_since_midnight']


class Manager(object):
    def __init__(self, router, screen, machine, check_interval):
        self.router = router
        self.screen = screen
        self.planner = Planner(screen)
        self.machine = machine
        self.check_interval = check_interval

        self.screen.manager = self
        self.planner.manager = self

    def start(self):
        """
        Start asynchronous jobs.
        """

        log.msg('Starting periodic status update...')
        self.status_loop = LoopingCall(self.send_status)
        self.status_loop.start(15, now=True)

        log.msg('Manager started.')

    def send_status(self):
        """
        Report telescreen status to the leader.
        """

        log.msg('Sending status update...')

        # FIXME: There should be a better mechanism to start a display
        #        standby timeout. Dimming it immediately is also not ideal.
        if len(self.planner.playing_items) == 0:
            self.poweroff()

        # FIXME: The `id` field should be something more volatile.
        #        It is there not to identity the device, but the message.
        message = {
            'id': uuid4().hex,
            'type': 'status',
            'status': {
                'power': get_power_status() in ('on', 'to-on'),
                'type': self.screen.mode,
            },
        }

        if self.screen.sidebar_uri is not None:
            message['status']['urlRight'] = self.screen.sidebar_uri

        if self.screen.panel_uri is not None:
            message['status']['urlBottom'] = self.screen.panel_uri

        self.router.send(message)

    def on_message(self, message, sender):
        """
        Handle incoming message from the leader.

        Validates the message against the `message-schema.yaml` and
        passes its contents to a correct method (called `on_<type>`).
        """

        try:
            validate(message, message_schema)
        except ValidationError as e:
            log.msg('Invalid message received: {}'.format(repr(message)))
            return

        log.msg('Received {} message...'.format(message['type']))
        handler = 'on_' + message['type']

        if hasattr(self, handler):
            payload = message.get(message['type'], {})
            reactor.callLater(0, getattr(self, handler), payload)
        else:
            log.msg('Message {} not implemented.'.format(message['type']))

    def on_resolution(self, resolution):
        """
        Leader requests that we change our layout.
        """

        self.screen.set_mode(resolution.get('type', 'full'))
        self.screen.set_sidebar_uri(resolution.get('urlRight'))
        self.screen.set_panel_uri(resolution.get('urlBottom'))

    def on_plan(self, plan):
        """Leader requests that we adjust out plan."""
        self.planner.change_plan(plan)

    def poweron(self, force=False):
        """
        Wake up all connected devices.
        """

        if get_power_status() not in ('on', 'to-on'):
            log.msg('Turning connected displays on...')
            set_power_status('on')

    def poweroff(self, force=False):
        """
        Standby all connected devices.
        """

        if get_power_status() not in ('standby', 'to-standby'):
            log.msg('Turning connected displays off...')
            set_power_status('standby')


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

        log.msg('Scheduled {} items.'.format(len(plan)))

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
