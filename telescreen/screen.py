#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Screen', 'VideoImage', 'ItemImage', 'init']

# Use GObject-Introspection for the Gtk infrastructure bindings.
# We are going to use Clutter and ClutterGst that are normally not exposed.
import gi

# Specify versions of components we are going to use.
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Clutter', '1.0')
gi.require_version('ClutterGst', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GObject', '2.0')

# Import Gtk infrastructure libraries that need initialization.
from gi.repository import ClutterGst
from gi.repository import GObject
from gi.repository import Gdk

# Import individual gi objects we need.
from gi.repository.Clutter import Actor, Stage, BinLayout, BinAlignment, \
    Image, ContentGravity, Color, StaticColor
from gi.repository.ClutterGst import Content
from gi.repository.Gst import parse_launch, State, MessageType
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.Cogl import PixelFormat

from twisted.internet import reactor
from twisted.python import log

from urllib.parse import quote
from os.path import dirname


class Screen(object):
    def __init__(self):
        self.stage = Stage.new()
        self.stage.set_fullscreen(True)
        self.stage.connect('delete-event', self.on_delete)

        self.stage.set_background_color(Color.get_static(StaticColor.BLACK))
        self.set_logo(dirname(__file__) + '/logo.png')

        self.actor = None
        self.pipeline = None

    def start(self):
        self.stage.show()
        log.msg('Screen started.')

    def on_delete(self, target, event):
        if self.pipeline is not None:
            self.pipeline.set_state(State.NULL)

        reactor.stop()

    def set_logo(self, path):
        self.stage.set_content(clutter_image_from_file(path))
        self.stage.set_content_gravity(ContentGravity.CENTER)


class Item(object):
    def __init__(self, planner, uri):
        self.screen = planner.screen
        self.planner = planner
        self.uri = uri

        self.state = 'stopped'
        self.pipeline = self.make_pipeline(uri)
        self.sink = self.pipeline.get_by_name('sink')

        content = Content.new_with_sink(self.sink)

        self.actor = Actor.new()
        self.actor.set_opacity(0)
        self.actor.set_content(content)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect('message', self.on_message)

        self.actor.connect('transition-stopped', self.on_actor_transition_stopped)

    def make_pipeline(self, uri):
        raise NotImplementedError('make_pipeline')

    def play(self):
        self.pipeline.set_state(State.PLAYING)

    def pause(self):
        self.pipeline.set_state(State.PAUSED)

    def stop(self):
        self.pipeline.set_state(State.NULL)

    def appear(self):
        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(255)
        self.actor.restore_easing_state()

    def disappear(self):
        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(0)
        self.actor.restore_easing_state()

    def on_message(self, bus, msg):
        if MessageType.EOS == msg.type:
            self.stop()
            return self.planner.stopped(self)

        if MessageType.STATE_CHANGED == msg.type:
            old, new, pending = msg.parse_state_changed()

            if new == new.PLAYING and self.state != 'playing':
                fit_actor_to_parent(self.actor)
                self.state = 'playing'
                return self.planner.playing(self)

            if new in (new.READY, new.PAUSED) and self.state != 'paused':
                fit_actor_to_parent(self.actor)
                self.state = 'paused'
                return self.planner.paused(self)

            if new == new.NULL and self.state != 'stopped':
                self.state = 'stopped'
                return self.planner.stopped(self)

    def on_actor_transition_stopped(self, actor, name, finished):
        if 'opacity' == name:
            if 0 == actor.get_opacity():
                return self.planner.disappeared(self)

            if 255 == actor.get_opacity():
                return self.planner.appeared(self)

    def __repr__(self):
        return '{0}(uri={1!r})'.format(type(self).__name__, self.uri)


class ImageItem(Item):
    def make_pipeline(self, uri):
        return parse_launch('''
            uridecodebin uri=%s buffer-size=20971520 name=source
                ! imagefreeze
                ! videoscale
                ! videoconvert
                ! cluttersink name=sink
        '''.strip() % quote(uri, '/:'))


class VideoItem(Item):
    def make_pipeline(self, uri):
        launch = '''
            uridecodebin uri=%s buffer-size=20971520 name=source
                ! videoconvert
                ! cluttersink name=sink
        '''.strip() % quote(uri, '/:')
        return parse_launch(launch)


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


def fit_actor_to_parent(actor):
    content = actor.get_content()
    if content is None:
        return

    applies, width, height = content.get_preferred_size()
    if not applies:
        return

    if actor.get_parent() is None:
        return

    parent_width = actor.get_parent().get_width()
    parent_height = actor.get_parent().get_height()

    width_ratio = float(parent_width) / float(width)
    height_ratio = float(parent_height) / float(height)

    width = int(width * min(width_ratio, height_ratio))
    height = int(height * min(width_ratio, height_ratio))

    actor.set_width(width)
    actor.set_height(height)

    actor.set_x((parent_width - width) / 2)
    actor.set_y((parent_height - height) / 2)


def init(argv):
    # Initialize Gdk.
    argv = Gdk.init(argv)

    # Initialize both Clutter and Gst.
    r, argv = ClutterGst.init(argv)
    if r.SUCCESS != r:
        exit(1)

    # Return remaining arguments.
    return argv


# vim:set sw=4 ts=4 et:
