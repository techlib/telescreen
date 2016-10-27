#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Screen', 'VideoImage', 'ItemImage', 'init']

# Use GObject-Introspection for the Gtk infrastructure bindings.
# We are going to use Clutter and ClutterGst that are normally not exposed.
import gi

# Import individual gi objects we need.
from gi.repository.Clutter import Actor, Stage, BinLayout, BinAlignment, \
    Image, ContentGravity, Color, StaticColor
from gi.repository.ClutterGst import Content
from gi.repository.Gst import parse_launch, State, MessageType
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.Cogl import PixelFormat

# Import Gtk infrastructure libraries that need initialization.
from gi.repository.GtkClutter import Embed
from gi.repository.Gtk import Fixed, ApplicationWindow, main_quit
from gi.repository.WebKit2 import WebView

from twisted.internet import reactor
from twisted.python import log

from urllib.parse import quote
from os.path import dirname


class Screen(ApplicationWindow):
    def __init__(self):
        super(Screen, self).__init__(title="Telescreen")
        self.mode = 1
        self.count = 0

        self.fixed = Fixed.new()
        self.player = Embed.new()

        self.right = WebView()
        self.bottom = WebView()

        self.stage = self.player.get_stage()
        self.stage.set_size(1920, 1080)

        self.stage.set_background_color(Color.get_static(StaticColor.BLACK))
        self.set_logo(dirname(__file__) + '/logo.png')

        self.fixed.add(self.player)
        self.fixed.add(self.right)
        self.fixed.add(self.bottom)

        self.add(self.fixed)

        self.connect('delete-event', self.on_delete)
        self.connect('check-resize', self.on_resize)

    def start(self):
        self.fullscreen()
        self.show_all()

        log.msg('Screen started.')

    def on_resize(self, widget):
        width, height = widget.get_size()
        if width <= 0 or width < height or height <= 0:
            return

        self.count += 1
        self.mode = self.mode % 3 + 1

        if self.mode == 1:
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(width, height)
            self.stage.set_size(width, height)
            self.right.hide()
            self.bottom.hide()

        elif self.mode == 2:
            self.right.load_uri('http://localhost:7070/custom?get=%s' % self.count)
            size = height/3*4
            self.player.show()
            self.stage.set_size(size, height)
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height)

            self.right.show()
            self.fixed.move(self.right, size, 0)
            self.right.set_size_request(width-size, height)

            self.bottom.hide()

        elif self.mode == 3:
            self.right.load_uri('http://localhost:7070/custom?get=%s' % self.count)
            self.bottom.load_uri('http://localhost:7070/custom?get=%s' % self.count)

            line = height / 12
            size = (height-line)*4/3

            self.fixed.move(self.player, 0, 0)
            self.player.show()
            self.player.set_size_request(size, height-line)
            self.stage.set_size(size, height)

            self.right.show()
            self.fixed.move(self.right, size, 0)
            self.right.set_size_request(width-size, height-line)

            self.bottom.show()
            self.fixed.move(self.bottom, 0, height-line)
            self.bottom.set_size_request(width, line)

    def on_delete(self, target, event):

        reactor.stop()
        main_quit()

    def on_click(self, widget):
        self.mode = self.mode % 3 + 1

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
        self.disappear()

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

        fit_actor_to_parent(self.actor)

        if MessageType.STATE_CHANGED == msg.type:
            old, new, pending = msg.parse_state_changed()

            if new == new.PLAYING and self.state != 'playing':
                self.state = 'playing'
                return self.planner.playing(self)

            if new in (new.READY, new.PAUSED) and self.state != 'paused':
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
            ! videoscale
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

    parent = actor.get_parent()
    if parent is None:
        return

    ratio = width/height

    parent_width = parent.get_width()
    parent_height = parent.get_height()

    if ratio >= 1:
        width = parent_width
        height = parent_width / ratio
    else:
        height = parent_height
        width = parent_height * ratio

    actor.set_width(width)
    actor.set_height(height)

    actor.set_x((parent_width-width)/2)
    actor.set_y((parent_height-height)/2)

# vim:set sw=4 ts=4 et:
