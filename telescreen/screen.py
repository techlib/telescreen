#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import WebKit2

from twisted.internet import reactor
from twisted.python import log

from urllib.parse import quote
from os.path import dirname

from telescreen.decoder.client import DecoderClient


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

        self.sidebar = WebKit2.WebView()
        self.fixed.add(self.sidebar)

        self.panel = WebKit2.WebView()
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
    Playlist item with its associated DrawingArea and a decoder.
    """

    def __init__(self, url):
        self.url = url
        self.stage = None
        self.decoder = None

    def prepare(self, screen):
        """
        Prepare the Item for playback by DrawingArea construction.
        """

        if self.stage is not None:
            log.msg('Cannot prepare Item twice, ignoring.')
            return

        self.stage = Gtk.DrawingArea()
        self.stage.set_double_buffered(False)

        #
        # FIXME: Find a better way to hide stage before the playback starts.
        #        Ideally hide it with another widget.
        #
        # Put the stage as a 1x1 pixel in the top-left corner of the screen
        # put it behind any active content that will cover it. The only
        # moment when it will not will be 5s before playback starts anew.
        #
        self.stage.set_size_request(0, 0)
        self.stage.set_halign(Gtk.Align.START)
        self.stage.set_valign(Gtk.Align.START)

        self.stage.connect('realize', self.on_realize)
        self.stage.show()

        screen.bin.add_overlay(self.stage)
        screen.bin.reorder_overlay(self.stage, 0)

    def on_realize(self, stage):
        """
        Called when the DrawingArea (stage) gets realized.

        With its XID known, launches a Decoder process (controlled using
        a DecoderClient instance) and immediately instruct it to preroll
        the pipeline.
        """

        self.xid = self.stage.get_window().get_xid()
        self.decoder = DecoderClient(self.xid, self.MEDIA, self.url)
        self.decoder.prepare()

    def make_pipeline(self, url):
        """Create GStreamer pipeline for playback of this item."""
        raise NotImplementedError('make_pipeline')

    def start(self):
        """
        Start playing the item and make the actor appear.
        """

        if self.decoder is None:
            log.msg('Cannot start without a Decoder, ignoring.')
            return

        # Start playback.
        self.decoder.play()

        # Bring the stage forward and allow it to expand.
        self.stage.set_size_request(-1, -1)
        self.stage.set_halign(Gtk.Align.FILL)
        self.stage.set_valign(Gtk.Align.FILL)
        self.stage.get_parent().reorder_overlay(self.stage, 1)

    def stop(self):
        """
        Stop pipeline and make the actor disappear.
        """

        if self.decoder is None:
            return

        self.decoder.stop()

        self.stage.get_parent().remove(self.stage)

        self.decoder = None
        self.stage = None

    def __repr__(self):
        return '{}(url={!r})'.format(type(self).__name__, self.url)


class ImageItem(Item):
    """Still image playlist item."""
    MEDIA = 'image'


class VideoItem(Item):
    """Video playlist item."""
    MEDIA = 'video'


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
