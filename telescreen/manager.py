#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.task import LoopingCall
from twisted.internet.error import AlreadyCalled
from twisted.internet import reactor
from twisted.python import log

from functools import *
from datetime import datetime
from jsonschema import validate, ValidationError
from uuid import uuid4

from telescreen.schema import schema
from telescreen.scheduler import Scheduler
from telescreen.screen import VideoItem, ImageItem


__all__ = ['Manager', 'seconds_since_midnight']


class Manager(object):
    def __init__(self, router, screen, cec):
        self.router = router
        self.screen = screen
        self.cec = cec

        # Generate new session identifier, we have just started.
        # When this changes, the next 'status' message will cause
        # leader to send us new plan.
        self.session = uuid4().hex

        # Create item playback scheduler.
        self.scheduler = Scheduler(screen)

    def start(self):
        """
        Start asynchronous jobs.
        """

        # Scheduler has its own periodic tasks.
        self.scheduler.start()

        # CEC has its tasks as well.
        self.cec.start()

        log.msg('Starting periodic status update...')
        self.status_loop = LoopingCall(self.send_status)
        self.status_loop.start(15, now=True)

        log.msg('Manager started.')

    def send_status(self):
        """
        Report telescreen status to the leader.
        """

        log.msg('Sending status update...')
        self.router.send({
            'id': uuid4().hex,
            'type': 'status',
            'status': {
                'session': self.session,
                'layout': self.screen.layout,
                'power': self.cec.status in ('on', 'to-on'),
            },
        })

    def on_message(self, message, sender):
        """
        Handle incoming message from the leader.

        Validates the message against the `message-schema.yaml` and
        passes its contents to a correct method (called `on_<type>`).
        """

        try:
            validate(message, schema)
        except ValidationError as e:
            log.err('Invalid message received: {}'.format(repr(message)))
            log.err(e.path)
            return

        log.msg('Received {} message...'.format(message['type']))
        handler = 'on_' + message['type']

        if hasattr(self, handler):
            payload = message.get(message['type'], {})
            reactor.callLater(0, getattr(self, handler), payload)
        else:
            log.err('Message {} not implemented.'.format(message['type']))

    def on_layout(self, layout):
        """Leader requests that we change our layout."""
        reactor.callLater(0, self.screen.set_layout, layout)

    def on_plan(self, plan):
        """Leader requests that we adjust out plan."""
        reactor.callLater(0, self.scheduler.change_plan, plan)

# vim:set sw=4 ts=4 et:
