#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

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


__all__ = ['Screen', 'VideoItem', 'ImageItem', 'AudioVideoItem']


class Screen(ApplicationWindow):
    """
    Window of the content player.
    """

    def __init__(self):
        super().__init__(title='Telescreen')
        self.mode = 'full'

        self.fixed = Fixed.new()
        self.player = Embed.new()

        self.sidebar = WebView()
        self.panel = WebView()

        self.stage = self.player.get_stage()
        self.stage.set_size(1920, 1080)

        self.stage.set_background_color(Color.get_static(StaticColor.BLACK))
        self.set_logo(dirname(__file__) + '/logo.png')

        self.fixed.add(self.player)
        self.fixed.add(self.sidebar)
        self.fixed.add(self.panel)

        self.manager = None
        self.add(self.fixed)

        self.connect('delete-event', self.on_delete)
        self.connect('check-resize', self.on_resize)

        self.sidebar_uri = None
        self.panel_uri = None

    def start(self):
        """
        Show the application window and start any periodic processes.
        """

        log.msg('Showing the player window...')
        self.fullscreen()
        self.show_all()
        self.on_resize(self)

        log.msg('Screen started.')

    def on_resize(self, widget):
        """
        Window has been resized.

        Calculate position of elements with respect to new window size
        and configured layout mode.
        """

        width, height = widget.get_size()
        if width <= 0 or width < height or height <= 0:
            return

        if self.mode == 'full':
            self.player.show()
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(width, height)
            self.stage.set_size(width, height)

            self.sidebar.hide()
            self.panel.hide()

        elif self.mode == 'right':
            size = height / 3 * 4

            self.player.show()
            self.stage.set_size(size, height)
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height)

            self.sidebar.show()
            self.fixed.move(self.sidebar, size, 0)
            self.sidebar.set_size_request(width-size, height)

            self.panel.hide()

        elif self.mode == 'both':
            panel = height / 12
            size = (height - panel) * 4 / 3

            self.player.show()
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height - panel)
            self.stage.set_size(size, height)

            self.sidebar.show()
            self.fixed.move(self.sidebar, size, 0)
            self.sidebar.set_size_request(width - size, height - panel)

            self.panel.show()
            self.fixed.move(self.panel, 0, height - panel)
            self.panel.set_size_request(width, panel)

    def on_delete(self, target, event):
        """
        Window has been closed.

        Stop the Twisted reactor and terminate the Gtk main loop.
        This should stop the application.
        """

        log.msg('Window closed, stopping reactor...')
        reactor.stop()
        main_quit()

        log.msg('Bye.')

    def set_logo(self, path):
        """
        Set the background logo on the stage.
        """

        self.stage.set_content(clutter_image_from_file(path))
        self.stage.set_content_gravity(ContentGravity.CENTER)

    def set_mode(self, mode):
        self.mode = mode
        self.on_resize(self)

    def set_sidebar_uri(self, uri):
        self.sidebar_uri = uri

        if uri is not None:
            self.sidebar.load_uri(uri)

    def set_panel_uri(self, uri):
        self.panel_uri = uri

        if uri is not None:
            self.panel.load_uri(uri)


class Item(object):
    """
    Playlist item with its associated Actor and GStreamer pipeline.
    """

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

        self.actor.connect('transition-stopped',
                           self.on_actor_transition_stopped)

    def make_pipeline(self, uri):
        """Create GStreamer pipeline for playback of this item."""
        raise NotImplementedError('make_pipeline')

    def play(self):
        """
        Stop all playing items and start playing this one.
        """

        for item in self.planner.playing_items:
            if item is not self:
                item.stop()

        self.planner.playing_items.append(self)
        self.planner.next()
        self.planner.manager.send_status()
        self.pipeline.set_state(State.PLAYING)
        self.planner.manager.poweron()

    def pause(self):
        """Pause the pipeline without touching the actor."""
        self.pipeline.set_state(State.PAUSED)

    def stop(self):
        """
        Stop pipeline and make the actor disappear.
        """

        self.pipeline.set_state(State.NULL)
        if self in self.planner.playing_items:
            self.planner.playing_items.remove(self)

        self.disappear()

    def appear(self):
        """
        Make actor appear smoothly.
        """

        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(255)
        self.actor.restore_easing_state()

    def disappear(self):
        """
        Make actor disappear smoothly.
        """

        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(0)
        self.actor.restore_easing_state()

    def on_message(self, bus, msg):
        """
        Handle message from GStreamer message bus.
        """

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
            log.err('GST Error: %s %s' % (err, debug))

    def on_actor_transition_stopped(self, actor, name, finished):
        """
        Actor stopped its fade in/out transition.
        """

        if 'opacity' == name:
            if 0 == actor.get_opacity():
                return self.planner.disappeared(self)

            if 255 == actor.get_opacity():
                return self.planner.appeared(self)

    def __repr__(self):
        return '{0}(uri={1!r})'.format(type(self).__name__, self.uri)


class ImageItem(Item):
    """Still image playlist item."""

    def make_pipeline(self, uri):
        return parse_launch("""
            uridecodebin uri=%s buffer-size=20971520 name=source
                ! imagefreeze
                ! videoscale
                ! cluttersink name=sink
        """.strip() % quote(uri, '/:'))


class VideoItem(Item):
    """Video playlist item."""

    def make_pipeline(self, uri):
        return parse_launch("""
            uridecodebin
                uri=%s
                buffer-size=20971520
                name=source
            ! videoconvert
            ! videoscale
            ! cluttersink name=sink
        """.strip() % quote(uri, '/:'))


# FIXME: We should not need a separate AudioVideoItem, VideoItem
#        should be enough for us!

class AudioVideoItem(Item):
    """Video with audio playlist item."""

    def make_pipeline(self, uri):
        return parse_launch("""
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
        """.strip() % quote(uri, '/:'))


def clutter_image_from_file(path):
    """
    Create clutter Image from a file on disk using GdkPixbuf.
    """

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
    """
    Adjust Actor position and size to best fit its parent.
    """

    content = actor.get_content()
    if content is None:
        return

    applies, width, height = content.get_preferred_size()
    if not applies:
        return

    parent = actor.get_parent()
    if parent is None:
        return

    ratio = width / height

    parent_width = parent.get_width()
    parent_height = parent.get_height()

    if ratio >= 1:
        width = parent_width
        height = parent_width / ratio
    else:
        width = parent_height * ratio
        height = parent_height

    actor.set_width(width)
    actor.set_height(height)

    actor.set_x((parent_width - width) / 2)
    actor.set_y((parent_height - height) / 2)


# vim:set sw=4 ts=4 et:
