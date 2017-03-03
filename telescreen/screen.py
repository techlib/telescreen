#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

# Import individual gi objects we need.
from gi.repository.Clutter import Actor, Stage, BinLayout, BinAlignment, \
                                  Image, ContentGravity, Color, StaticColor
from gi.repository.ClutterGst import Content
from gi.repository.Gst import parse_launch, Pipeline, ElementFactory, State, \
                              MessageType, GhostPad, PadDirection
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

import gc


__all__ = ['Screen', 'VideoItem', 'ImageItem']


class Screen(ApplicationWindow):
    """
    Window of the content player.
    """

    def __init__(self):
        super().__init__(title='Telescreen')
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

        self.add(self.fixed)

        self.connect('delete-event', self.on_delete)
        self.connect('check-resize', self.on_resize)

        self.layout = {
            'mode': 'full',
            'sidebar': None,
            'panel': None,
        }

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

        if self.layout['mode'] == 'full':
            self.player.show()
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(width, height)
            self.stage.set_size(width, height)

            self.sidebar.hide()
            self.panel.hide()

        elif self.layout['mode'] == 'sidebar':
            size = height / 3 * 4

            self.player.show()
            self.stage.set_size(size, height)
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height)

            self.sidebar.show()
            self.fixed.move(self.sidebar, size, 0)
            self.sidebar.set_size_request(width - size, height)

            self.panel.hide()

        elif self.layout['mode'] == 'panel':
            panel = height / 12
            size = (height - panel) * 4 / 3

            self.player.show()
            self.fixed.move(self.player, 0, 0)
            self.player.set_size_request(size, height - panel)
            self.stage.set_size(size, height - panel)

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

    def set_layout(self, layout):
        """
        Change the screen layout.

        Layout is a dictionary with ``mode``, ``sidebar``, and ``panel`` keys.
        Valid values for ``mode`` are ``full``, ``sidebar``, and ``panel``.

        - ``full`` represents a fullscreen video with no web content.
        - ``sidebar`` shrinks video to 4:3 and adds a web sidebar.
        - ``panel`` builds on the ``sidebar`` and adds a bottom web panel.

        Both ``sidebar`` and ``panel`` key values are valid URLs or None.
        """

        if self.layout != layout:
            self.layout = layout
            self.on_resize(self)

            self.sidebar.load_uri(layout.get('sidebar') or 'about:blank')
            self.panel.load_uri(layout.get('panel') or 'about:blank')


class Item:
    """
    Playlist item with its associated Actor and GStreamer pipeline.
    """

    def __init__(self, url):
        self.url = url

        self.pipeline = None
        self.sink = None
        self.actor = None
        self.bus = None

    def prepare(self, screen):
        assert self.pipeline is None, 'Cannot prepare Item twice'

        self.pipeline, self.sink = self.make_pipeline(self.url)

        content = Content.new_with_sink(self.sink)

        self.actor = Actor.new()
        self.actor.set_opacity(0)
        self.actor.set_content(content)
        screen.stage.add_child(self.actor)
        self.actor.connect('transition-stopped', remove_actor_after_fade_out)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_message)

        self.pipeline.set_state(State.PAUSED)

    def make_pipeline(self, url):
        """Create GStreamer pipeline for playback of this item."""
        raise NotImplementedError('make_pipeline')

    def start(self):
        """
        Start playing the item and make the actor appear.
        """

        assert self.pipeline is not None, 'Cannot start unprepared Item'

        self.pipeline.set_state(State.PLAYING)

        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(255)
        self.actor.restore_easing_state()

        # Collect the garbage to prevent excessive memory use due to
        # large memory structures of the foreign Gst objects.
        gc.collect()

    def stop(self):
        """
        Stop pipeline and make the actor disappear.
        """

        if self.pipeline is None:
            return

        self.pipeline.set_state(State.NULL)
        self.bus.remove_signal_watch()

        self.actor.save_easing_state()
        self.actor.set_easing_duration(240)
        self.actor.set_opacity(0)
        self.actor.restore_easing_state()

        self.pipeline = None
        self.sink = None
        self.bus = None
        self.actor = None

    def on_message(self, bus, msg):
        """
        Handle message from GStreamer message bus.
        """

        if MessageType.EOS == msg.type:
            self.stop()

        elif MessageType.STATE_CHANGED == msg.type:
            old, new, pending = msg.parse_state_changed()

            if old != new:
                fit_actor_to_parent(self.actor)

        elif MessageType.ERROR == msg.type:
            log.msg('GStreamer: {} {}'.format(*msg.parse_error()))
            self.stop()

    def __repr__(self):
        return '{}(url={!r})'.format(type(self).__name__, self.url)


class ImageItem(Item):
    """Still image playlist item."""

    def make_pipeline(self, url):
        pipeline = Pipeline()

        source = ElementFactory.make('playbin3')
        pipeline.add(source)

        videosink = parse_launch('''
            imagefreeze
            ! video/x-raw, pixel-aspect-ratio=1/1, rate=1/3600
            ! videoscale add-borders=true
            ! video/x-raw, height=[1,2048], pixel-aspect-ratio=1/1
            ! videoscale add-borders=true
            ! video/x-raw, width=[1,2048], pixel-aspect-ratio=1/1
            ! cluttersink name=sink
        ''')
        realpad = videosink.find_unlinked_pad(PadDirection.SINK)
        ghostpad = GhostPad.new(None, realpad)
        videosink.add_pad(ghostpad)

        cluttersink = videosink.get_by_name('sink')

        source.set_property('uri', quote(url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, cluttersink


class VideoItem(Item):
    """Video playlist item."""

    def make_pipeline(self, url):
        pipeline = Pipeline()

        # FIXME: We should use playbin3, but it seemed to fail sometimes.
        source = ElementFactory.make('playbin')
        pipeline.add(source)

        videosink = ElementFactory.make('cluttersink')

        source.set_property('uri', quote(url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, videosink


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

    parent_width = parent.get_width()
    parent_height = parent.get_height()

    width_ratio = float(parent_width) / float(width)
    height_ratio = float(parent_height) / float(height)
    ratio = min(width_ratio, height_ratio)

    width = int(width * ratio)
    height = int(height * ratio)

    actor.set_width(width)
    actor.set_height(height)

    actor.set_x((parent_width - width) / 2)
    actor.set_y((parent_height - height) / 2)


def remove_actor_after_fade_out(actor, name, finished):
    """
    Remove actor from its parent after it fades out.
    """

    if 'opacity' == name and 0 == actor.get_opacity():
        actor.get_parent().remove_child(actor)


# vim:set sw=4 ts=4 et:
