#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from datetime import datetime

from twisted.internet import reactor
from twisted.python import log

from telescreen.screen import VideoItem, ImageItem

class Manager(object):
    def __init__(self, router, screen):
        self.router = router
        self.screen = screen
        self.planner = Planner(screen)

    def start(self):
        #self.planner.play_image('http://www.techlib.cz/public/userfiles/Features/Písek web.jpg')
        self.planner.play_video('https://upload.wikimedia.org/wikipedia/commons/transcoded/b/b5/I-15bis.ogg/I-15bis.ogg.360p.webm')

        log.msg('Manager started.')


class Planner(object):
    def __init__(self, screen):
        self.screen = screen

    def playing(self, item):
        log.msg('Item %r playing.' % item.uri)
        item.appear()

    def paused(self, item):
        log.msg('Item %r paused.' % item.uri)
        item.play()

    def stopped(self, item):
        log.msg('Item %r stopped.' % item.uri)
        item.disappear()

    def appeared(self, item):
        log.msg('Item %r appeared.' % item.uri)

    def disappeared(self, item):
        log.msg('Item %r disappeared.' % item.uri)
        self.screen.stage.remove_child(item.actor)

    def play_video(self, uri):
        item = VideoItem(self, uri)
        self.screen.stage.add_child(item.actor)
        item.pause()

    def play_image(self, uri):
        item = ImageItem(self, uri)
        self.screen.stage.add_child(item.actor)
        item.pause()


def seconds_since_midnight():
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (now - midnight).total_seconds()


# vim:set sw=4 ts=4 et:
