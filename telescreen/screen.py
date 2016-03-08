#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from gi.repository.Clutter import Actor, Stage, BinLayout, BinAlignment
from gi.repository.ClutterGst import Content
from gi.repository.Gst import parse_launch, State

from twisted.internet import reactor
from twisted.python import log


class Screen(object):
    def __init__(self):
        self.stage = Stage.new()
        self.stage.connect('delete-event', self.on_delete)

        layout = BinLayout.new(BinAlignment.FILL, BinAlignment.FILL)
        self.stage.set_layout_manager(layout)

        self.pipeline = parse_launch('videotestsrc ! warptv ! cluttersink name=sink')
        sink = self.pipeline.get_by_name('sink')
        content = Content.new_with_sink(sink)

        self.actor = Actor.new()
        self.actor.set_content(content)
        self.actor.set_size(640, 480)

        self.stage.add_child(self.actor)

    def start(self):
        log.msg('Screen started.')

        self.pipeline.set_state(State.PLAYING)
        self.stage.show()

    def on_delete(self, target, event):
        self.pipeline.set_state(State.NULL)
        reactor.stop()


# vim:set sw=4 ts=4 et:
