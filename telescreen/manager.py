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
from os import uname

from telescreen.schema import schema
from telescreen.scheduler import ItemScheduler, LayoutScheduler, PowerScheduler
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
        self.item_scheduler = ItemScheduler(screen)

        # Create layout change scheduler.
        self.layout_scheduler = LayoutScheduler(screen)

        # Create power scheduled
        self.power_scheduler = PowerScheduler(cec)

        # Identifier of the last plan from the leader.
        self.plan = '0' * 32

        # More human readable identifier
        self.hostname = uname().nodename

    def start(self):
        """
        Start asynchronous jobs.
        """

        # Schedulers have their own periodic tasks.
        self.item_scheduler.start()
        self.layout_scheduler.start()
        self.power_scheduler.start()

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
                'plan': self.plan,
                'layout': self.screen.layout,
                'power': self.cec.status,
                'hostname': self.hostname
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
            if isinstance(message, dict):
                t = message.get('type')
                log.msg('Invalid message received, type {!r}.'.format(t))
            else:
                log.msg('Invalid message received, not an object.')

            return

        log.msg('Received {} message...'.format(message['type']))
        handler = 'on_' + message['type']

        if hasattr(self, handler):
            payload = message.get(message['type'], {})
            reactor.callLater(0, getattr(self, handler), payload)
        else:
            log.msg('Message {} not implemented.'.format(message['type']))

    def on_plan(self, plan):
        """
        Leader requests that we adjust out plan.
        """

        if plan['id'] == self.plan:
            log.msg('We already use plan {}, ignoring.'.format(self.plan))
            return

        self.plan = plan['id']

        items = plan['items']
        layouts = plan['layouts']
        power = plan['power']

        reactor.callLater(0, self.item_scheduler.change_plan, items)
        reactor.callLater(0, self.layout_scheduler.change_plan, layouts)
        reactor.callLater(0, self.power_scheduler.change_plan, power)

    def on_close(self):
        """
        Do what needs to be done before shutdown
        """

        log.msg('Closing Indoktrinator...')
        log.msg('Shutting down CEC...')
        self.cec.close()

# vim:set sw=4 ts=4 et:
