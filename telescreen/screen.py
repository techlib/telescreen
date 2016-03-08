#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from gi.repository.Clutter import Actor, Stage, BinLayout, BinAlignment, \
    Image, ContentGravity, Color, StaticColor
from gi.repository.ClutterGst import Content
from gi.repository.Gst import parse_launch, State
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.Cogl import PixelFormat

from twisted.internet import reactor
from twisted.python import log

from os.path import dirname


class Screen(object):
    def __init__(self):
        self.stage = Stage.new()
        self.stage.connect('delete-event', self.on_delete)

        layout = BinLayout.new(BinAlignment.FILL, BinAlignment.FILL)
        self.stage.set_layout_manager(layout)
        self.stage.set_background_color(Color.get_static(StaticColor.BLACK))

        self.set_logo(dirname(__file__) + '/logo.png')

        self.actor = None
        self.pipeline = None

    def start(self):
        def play():
            pipeline = parse_launch('videotestsrc ! warptv ! cluttersink name=sink')
            self.set_pipeline(pipeline)

        reactor.callLater(1, play)

        self.stage.show()
        log.msg('Screen started.')

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            self.pipeline.set_state(State.NULL)

        if pipeline is None:
            self.pipeline = None
            self.actor = None
            return

        assert pipeline.get_by_name('sink')

        self.pipeline = pipeline
        content = Content.new_with_sink(pipeline.get_by_name('sink'))

        self.actor = Actor.new()
        self.actor.set_content(content)
        self.actor.set_size(640, 480)
        self.stage.add_child(self.actor)

        self.pipeline.set_state(State.PLAYING)

    def on_delete(self, target, event):
        if self.pipeline is not None:
            self.pipeline.set_state(State.NULL)

        reactor.stop()

    def list_programs(self):
        raise NotImplementedError('list_programs')

    def change_program(self, program):
        raise NotImplementedError('change_program')

    def set_logo(self, path):
        self.stage.set_content(clutter_image_from_file(path))
        self.stage.set_content_gravity(ContentGravity.CENTER)


class Item(object):
    def __init__(self):
        pass


def clutter_image_from_file(path):
    pixbuf = Pixbuf.new_from_file(path)
    image = Image.new()

    if pixbuf.get_has_alpha():
        pixel_format = PixelFormat.RGBA_8888
    else:
        pixel_format = PixelFormat.RGB_888

    assert image.set_data(pixbuf.get_pixels(),
                          pixel_format,
                          pixbuf.get_width(),
                          pixbuf.get_height(),
                          pixbuf.get_rowstride())

    return image


# vim:set sw=4 ts=4 et:
