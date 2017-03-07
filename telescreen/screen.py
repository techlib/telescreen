#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from gi.repository.Gst import parse_launch, Pipeline, ElementFactory, State, \
                              MessageType, GhostPad, PadDirection

from gi.repository import Gst
from gi.repository import GstVideo
from gi.repository import Gdk
from gi.repository import Gtk

from gi.repository.WebKit2 import WebView

from twisted.internet import reactor
from twisted.python import log

from urllib.parse import quote
from os.path import dirname


__all__ = ['Screen', 'VideoItem', 'ImageItem']


class Screen:
    """
    Window of the content player.
    """

    def __init__(self):
        self.window = Gtk.ApplicationWindow(title='Telescreen')

        black = Gdk.RGBA()
        black.parse('#000000')
        self.window.override_background_color(Gtk.StateFlags.NORMAL, black)

        self.background = None

        self.fixed = Gtk.Fixed.new()
        self.window.add(self.fixed)

        self.bin = Gtk.Overlay()
        self.fixed.add(self.bin)

        image = Gtk.Image.new_from_file(dirname(__file__) + '/logo.png')
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        self.bin.add(image)

        self.sidebar = WebView()
        self.fixed.add(self.sidebar)

        self.panel = WebView()
        self.fixed.add(self.panel)

        self.window.connect('delete-event', self.on_delete)
        self.window.connect('check-resize', self.on_resize)
        self.window.connect('realize', self.on_realize)

        self.layout = {
            'mode': 'full',
            'sidebar': None,
            'panel': None,
        }

        self.xid = None

    def start(self):
        """
        Show the application window and start any periodic processes.
        """

        log.msg('Showing the player window...')
        self.window.fullscreen()
        self.window.show_all()
        self.on_resize(self.window)

        log.msg('Screen started.')

    def on_realize(self, window):
        cursor = Gdk.Cursor.new(Gdk.CursorType.BLANK_CURSOR)
        window.get_window().set_cursor(cursor)

    def on_resize(self, widget):
        """
        Window has been resized.

        Calculate position of elements with respect to new window size
        and configured layout mode.
        """

        width, height = widget.get_size()

        if width < 0 or height < 0:
            return

        if self.layout['mode'] == 'full':
            self.fixed.move(self.bin, 0, 0)
            self.bin.set_size_request(width, height)

            self.sidebar.hide()
            self.panel.hide()

        elif self.layout['mode'] == 'sidebar':
            size = height / 3 * 4

            self.fixed.move(self.bin, 0, 0)
            self.bin.set_size_request(size, height)

            self.sidebar.show()
            self.fixed.move(self.sidebar, size, 0)
            self.sidebar.set_size_request(width - size, height)

            self.panel.hide()

        elif self.layout['mode'] == 'panel':
            panel = height / 12
            size = (height - panel) * 4 / 3

            self.fixed.move(self.bin, 0, 0)
            self.bin.set_size_request(size, height - panel)

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
        Gtk.main_quit()

        log.msg('Bye.')

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
            self.on_resize(self.window)

            self.sidebar.load_uri(layout.get('sidebar') or 'about:blank')
            self.panel.load_uri(layout.get('panel') or 'about:blank')


class Item:
    """
    Playlist item with its associated DrawingArea and GStreamer pipeline.
    """

    def __init__(self, url):
        self.url = url

        self.pipeline = None
        self.sink = None
        self.stage = None
        self.bus = None

    def prepare(self, screen):
        assert self.pipeline is None, 'Cannot prepare Item twice'

        self.pipeline, self.sink = self.make_pipeline(self.url)

        self.stage = Gtk.DrawingArea()
        self.stage.set_double_buffered(True)
        self.stage.set_halign(Gtk.Align.CENTER)
        self.stage.set_valign(Gtk.Align.CENTER)

        # Use zero-sized window to draw the initial frame of the video.
        # We need to preroll the video and zero opacity does not affect
        # video overlays. We resize it later on.
        self.stage.set_size_request(0, 0)

        self.stage.connect('realize', self.on_realize)
        self.stage.show()

        #self.stage.set_opacity(0)
        screen.bin.add_overlay(self.stage)
        #self.stage.connect('transition-stopped', remove_actor_after_fade_out)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_message)

    def on_realize(self, stage):
        self.xid = self.stage.get_window().get_xid()
        self.sink.set_window_handle(self.xid)
        self.pipeline.set_state(State.PAUSED)

    def make_pipeline(self, url):
        """Create GStreamer pipeline for playback of this item."""
        raise NotImplementedError('make_pipeline')

    def start(self):
        """
        Start playing the item and make the actor appear.
        """

        if self.pipeline is None:
            log.msg('Cannot start unprepared Item, bailing out.')
            return

        if self.xid is None:
            log.msg('Cannot start without a realized stage, bailing out.')
            return

        self.pipeline.set_state(State.PLAYING)

        # Pipeline has been rendering to a zero-sized stage.
        self.stage.set_size_request(-1, -1)
        self.stage.set_halign(Gtk.Align.FILL)
        self.stage.set_valign(Gtk.Align.FILL)

    def stop(self):
        """
        Stop pipeline and make the actor disappear.
        """

        if self.pipeline is None:
            return

        self.pipeline.set_state(State.NULL)
        self.bus.remove_signal_watch()
        self.stage.get_parent().remove(self.stage)

        self.pipeline = None
        self.sink = None
        self.bus = None
        self.stage = None

    def on_message(self, bus, msg):
        """
        Handle message from GStreamer message bus.
        """

        if MessageType.EOS == msg.type:
            self.stop()

        elif MessageType.STATE_CHANGED == msg.type:
            old, new, pending = msg.parse_state_changed()

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
            ! xvimagesink name=sink
        ''')
        realpad = videosink.find_unlinked_pad(PadDirection.SINK)
        ghostpad = GhostPad.new(None, realpad)
        videosink.add_pad(ghostpad)

        realsink = videosink.get_by_name('sink')

        source.set_property('uri', quote(url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, realsink


class VideoItem(Item):
    """Video playlist item."""

    def make_pipeline(self, url):
        pipeline = Pipeline()

        # FIXME: We should use playbin3, but it seemed to fail sometimes.
        source = ElementFactory.make('playbin')
        pipeline.add(source)

        videosink = ElementFactory.make('xvimagesink')

        source.set_property('uri', quote(url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, videosink


def image_from_file(path):
    """
    Create Image from a file on disk.
    """

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
