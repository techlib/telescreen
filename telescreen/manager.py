#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from twisted.internet.task import LoopingCall
from twisted.internet.error import AlreadyCalled
from twisted.internet import reactor
from twisted.python import log

from datetime import datetime
from jsonschema import validate, ValidationError

from telescreen.screen import VideoItem, ImageItem


class Manager(object):
    def __init__(self, screen, machine):
        self.client = None
        self.screen = screen
        self.planner = Planner(screen)
        self.machine = machine

    def start(self):
        log.msg('Manager started.')
        #self.client.init()


class Planner(object):
    def __init__(self, screen):
        self.screen = screen
        self.schedule = set()
        self.events = []

        #reactor.callLater(2, self.init)

    #def init(self):
        #'''
        #pass
        #'''
        #item = ImageItem(self, 'http://10.93.0.95:7070/media/img.jpg')
        #self.schedule_item(item, seconds_since_midnight()+1, seconds_since_midnight()+2)

        #item = VideoItem(self, 'http://10.93.0.95:7070/media/Crazy-Frog.mpg')
        #self.schedule_item(item, seconds_since_midnight()+2, seconds_since_midnight()+60)

        #item = ImageItem(self, 'http://10.93.0.95:7070/media/img2.jpg')
        #self.schedule_item(item, seconds_since_midnight()+10, seconds_since_midnight()+15)

        #item = ImageItem(self, 'http://10.93.0.95:7070/media/img.jpg')
        #self.schedule_item(item, seconds_since_midnight()+15, seconds_since_midnight()+20)

    def change_plan(self, plan):
        for event in self.events:
            try:
                event.cancel()
            except AlreadyCalled:
                pass

        self.events = []

        for item in self.schedule:
            item.stop()
            self.screen.stage.remove_child(item.actor)

        self.schedule = set()

        for data in plan:
            if data['type'] == 'video':
                item = VideoItem(self, data['uri'])
            elif data['type'] == 'image':
                item = ImageItem(self, data['uri'])
            else:
                log.msg('Unknown item type {0!r}'.format(kind))
                continue

            self.schedule.add(item)
            self.schedule_item(item, data['start'], data['end'])

    def schedule_item(self, item, start, end):
        self.schedule.add(item)
        self.screen.stage.add_child(item.actor)

        now = seconds_since_midnight()

        if end < now:
            return log.msg('Too late for {0!r}.'.format(item.uri))

        play_in = max(start - now, 0)
        pause_in = max(play_in - 30, 0)
        stop_in = max(end - now, 0)

        log.msg('Schedule {0!r} in {1!r}s.'.format(item.uri, play_in))

        if pause_in < play_in:
            self.events.append(reactor.callLater(pause_in, item.pause))

        self.events.append(reactor.callLater(play_in, item.play))
        self.events.append(reactor.callLater(stop_in, item.stop))

    def playing(self, item):
        log.msg('Item %r playing.' % item.uri)
        item.appear()

    def paused(self, item):
        log.msg('Item %r paused.' % item.uri)

    def stopped(self, item):
        log.msg('Item %r stopped.' % item.uri)
        item.disappear()

    def appeared(self, item):
        log.msg('Item %r appeared.' % item.uri)

    def disappeared(self, item):
        log.msg('Item %r disappeared.' % item.uri)
        self.screen.stage.remove_child(item.actor)


def seconds_since_midnight():
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (now - midnight).total_seconds()


# vim:set sw=4 ts=4 et:
