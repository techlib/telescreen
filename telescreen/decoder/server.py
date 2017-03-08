#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from gi.repository import Gst
from gi.repository import GstVideo

from twisted.internet import reactor
from twisted.protocols.basic import LineReceiver
from twisted.python import log

from urllib.parse import quote
from os import linesep


class Decoder (LineReceiver):
    delimiter = linesep.encode('utf8')

    def __init__(self, xid, media, url):
        self.xid = xid
        self.media = media
        self.url = url

        self.pipeline = None
        self.sink = None
        self.bus = None

    def connectionMade(self):
        log.msg('Starting media decoder...')
        self.sendLine(b'ready')

    def lineReceived(self, line):
        event = line.strip().decode('utf8')
        getattr(self, 'on_{}'.format(event), self.on_unknown)()

    def on_unknown(self):
        log.msg('Received an unknown command, ignoring.')

    def on_prepare(self):
        if self.pipeline is not None:
            log.msg('Cannot prepare twice, ignoring.')
            return

        log.msg('Creating pipeline...')

        constructor = 'make_{}_pipeline'.format(self.media)
        self.pipeline, self.sink = getattr(self, constructor)()

        self.sink.set_window_handle(self.xid)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_bus_event)

        log.msg('Prerolling...')
        self.pipeline.set_state(Gst.State.PAUSED)

        self.sendLine(b'prepared')

    def on_play(self):
        if self.pipeline is None:
            self.on_prepare()

        log.msg('Starting playback...')
        self.pipeline.set_state(Gst.State.PLAYING)

        self.sendLine(b'playing')

    def on_stop(self):
        log.msg('Stopping nicely...')

        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)

        if reactor.running:
            reactor.stop()

    def connectionLost(self, reason):
        log.msg('Parent left us, exiting.')
        self.on_stop()

    def on_bus_event(self, bus, msg):
        if Gst.MessageType.EOS == msg.type:
            self.on_stop()

        elif Gst.MessageType.STATE_CHANGED == msg.type:
            old, new, pending = msg.parse_state_changed()

        elif Gst.MessageType.ERROR == msg.type:
            log.msg('GStreamer: {} {}'.format(*msg.parse_error()))
            self.on_stop()

    def make_image_pipeline(self):
        pipeline = Gst.Pipeline()

        source = Gst.ElementFactory.make('playbin3')
        pipeline.add(source)

        videosink = Gst.parse_launch('''
            imagefreeze
            ! videoscale add-borders=true
            ! xvimagesink name=sink
        ''')
        realpad = videosink.find_unlinked_pad(Gst.PadDirection.SINK)
        ghostpad = Gst.GhostPad.new(None, realpad)
        videosink.add_pad(ghostpad)

        realsink = videosink.get_by_name('sink')

        source.set_property('uri', quote(self.url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, realsink

    def make_video_pipeline(self):
        pipeline = Gst.Pipeline()

        # FIXME: We should use playbin3, but it seemed to fail sometimes.
        source = Gst.ElementFactory.make('playbin')
        pipeline.add(source)

        videosink = Gst.ElementFactory.make('xvimagesink')

        source.set_property('uri', quote(self.url, '/:'))
        source.set_property('buffer-size', 2**22)
        source.set_property('video-sink', videosink)

        return pipeline, videosink


# vim:set sw=4 ts=4 et:
