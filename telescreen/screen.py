#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

# Import individual gi objects we need.
import logging
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

__all__ = ['Screen', 'VideoImage', 'ItemImage', 'AudioVideoItem',]


class Screen(ApplicationWindow):
    '''
    Wrapper for main window. Contain all widget and map basic signals
    '''
    MODE_FULLSCREEN = 'full'
    MODE_RIGHT = 'right'
    MODE_BOTH = 'both'

    def __init__(self):
        '''
        Create basic object
        '''
        super(Screen, self).__init__(title="Telescreen")
        self.mode = Screen.MODE_FULLSCREEN
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

        self.manager = None
        self.add(self.fixed)

        self.connect('delete-event', self.on_delete)
        self.connect('check-resize', self.on_resize)

        self.url1 = None
        self.url2 = None

    def start(self):
        '''
        Start showing window
        '''
        self.fullscreen()
        self.show_all()

        log.msg('Screen started.')

    def on_resize(self, widget):
        '''
        On resize event calc proportion of clutter and webkit widget
        '''
        width, height = widget.get_size()
        if width <= 0 or width < height or height <= 0:
            return

        self.count += 1

        if self.mode == Screen.MODE_FULLSCREEN:
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(width, height)
            self.stage.set_size(width, height)
            self.right.hide()
            self.bottom.hide()

        elif self.mode == Screen.MODE_RIGHT:
            size = height/3*4
            self.player.show()
            self.stage.set_size(size, height)
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height)

            self.right.show()
            self.fixed.move(self.right, size, 0)
            self.right.set_size_request(width-size, height)

            self.bottom.hide()

        elif self.mode == Screen.MODE_BOTH:

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
        '''
        '''

        reactor.stop()
        main_quit()

    def set_logo(self, path):
        '''
        '''
        self.stage.set_content(clutter_image_from_file(path))
        self.stage.set_content_gravity(ContentGravity.CENTER)

    def setMode(self, mode):
        # Fit screen
        self.mode = mode
        self.on_resize(self)

    def setUrl1(self, url):
        self.url1 = url
        if url:
            self.right.load_uri(url)

    def setUrl2(self, url):
        self.url2 = url
        if url:
            self.bottom.load_uri(url)


class Item(object):
    PLAYING = 0

    def __init__(self, planner, uri):
        '''
        '''
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
        '''
        '''
        raise NotImplementedError('make_pipeline')

    def play(self):
        '''
        '''
        for item in self.planner.playing_items:
            if item is not self:
                item.stop()

        self.planner.playing_items.append(self)
        self.planner.next()
        self.planner.manager.client.status()
        self.pipeline.set_state(State.PLAYING)
        self.planner.manager.poweron()

    def pause(self):
        '''
        '''
        self.pipeline.set_state(State.PAUSED)

    def stop(self):
        '''

        '''
        self.pipeline.set_state(State.NULL)
        if self in self.planner.playing_items:
            self.planner.playing_items.remove(self)

        self.disappear()

    def appear(self):
        '''
        apear item
        '''
        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(255)
        self.actor.restore_easing_state()

    def disappear(self):
        '''
        Disaper item
        '''
        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(0)
        self.actor.restore_easing_state()

    def on_message(self, bus, msg):
        '''
        on message callback method
        '''
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

        elif MessageType.ERROR == msg.type:
            self.stop()
            # Posibility to show broken image
            err, debug = msg.parse_error()
            log.msg('GST Error: %s %s' % (err, debug), logLevel=logging.ERROR)

    def on_actor_transition_stopped(self, actor, name, finished):
        if 'opacity' == name:
            if 0 == actor.get_opacity():
                return self.planner.disappeared(self)

            if 255 == actor.get_opacity():
                return self.planner.appeared(self)

    def __repr__(self):
        return '{0}(uri={1!r})'.format(type(self).__name__, self.uri)


class ImageItem(Item):
    '''
    Image item pipeline commands
    '''
    def make_pipeline(self, uri):
        return parse_launch('''
            uridecodebin uri=%s buffer-size=20971520 name=source
                ! imagefreeze
                ! videoscale
                ! cluttersink name=sink
        '''.strip() % quote(uri, '/:'))


class VideoItem(Item):
    '''
    Video item pipeline commands
    '''
    def make_pipeline(self, uri):
        launch = '''
            uridecodebin
                uri=%s
                buffer-size=20971520
                name=source
            ! videoconvert
            ! videoscale
            ! cluttersink name=sink
        '''.strip() % quote(uri, '/:')
        return parse_launch(launch)


class AudioVideoItem(Item):
    '''
    AudioVideo item pipeline commands
    '''
    def make_pipeline(self, uri):
        launch = '''
            uridecodebin
                uri=%s
                buffer-size=20971520
                name=source

            source.
            ! queue
            ! audioconvert
            ! audioresample
            ! pulsesink

            source.
            ! queue
            ! videoconvert
            ! videoscale
            ! cluttersink name=sink
        '''.strip() % quote(uri, '/:')
        return parse_launch(launch)


def clutter_image_from_file(path):
    '''
    Generate clutter image from binary
    '''
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
    '''
    Calc proportion af actor
    '''
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
