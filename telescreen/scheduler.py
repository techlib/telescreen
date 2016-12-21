#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.error import AlreadyCalled
from twisted.internet.task import LoopingCall
from twisted.internet import reactor
from twisted.python import log

from time import time
from datetime import datetime

from telescreen.screen import VideoItem, ImageItem
from telescreen.cec import get_power_status, set_power_status


__all__ = ['Scheduler']


class Scheduler(object):
    """
    Executes planned items on the screen and handles display power.
    """

    ITEM_TYPES = {
        'video': VideoItem,
        'image': ImageItem,
    }

    def __init__(self, screen):
        self.screen = screen

        # The whole current plan.
        # Used only to detect changes when a new plan is installed.
        self.plan = []

        # Items remaining in the plan.
        self.queue = []

        # Items that are currently instantiated.
        self.items = set()

        # Scheduled events such as play and stop.
        self.events = set()

    def start(self):
        """
        Start periodic scheduling tasks.
        """

        log.msg('Starting scheduling loop...')
        self.scheduling_loop = LoopingCall(self.schedule)
        self.scheduling_loop.start(5)

        log.msg('Scheduler started.')

    def add_event(self, ts, fn, *args, **kwargs):
        """
        Schedule and register a cancellable event.
        """

        event = None
        delta = max(ts - time(), 0)

        def wrapper():
            self.events.discard(event)
            return fn(*args, **kwargs)

        event = reactor.callLater(delta, wrapper)

    def change_plan(self, plan):
        """
        Install new plan from the leader and immediately reschedule.
        """

        # First, sort the new plan by event start times.
        plan.sort(key=lambda item: item['start'])

        # FIXME: Rebase all the timestamps to the last midnight.
        #        This is something leader should do for us.
        midnight = last_midnight()

        for item in plan:
            item['start'] += midnight
            item['end'] += midnight

        # Queue will be modified, plan will stay as it is.
        queue = list(plan)

        # We need to make sure that the plan actually changed before
        # doing anything destructive, such as stopping current playback.
        now = time()
        cur = plan_window(self.plan, now, now + 60)
        new = plan_window(plan, now, now + 60)

        if cur != new:
            log.msg('Resetting schedule...')

            # Stop and get rid of all currently instantiated items.
            for item in list(self.items):
                self.items.discard(item)
                item.stop()

            # Cancel all pending events.
            for event in list(self.events):
                self.events.discard(event)
                event.cancel()

        else:
            log.msg('Adjusting schedule...')

            # Catch up with the current scheduling.
            self.schedule(now)

            # Work through the new queue up to the same point so that
            # the handoff will go smoothly and items won't overlap.
            pop_queue_items(queue, now=now)

        # Install new plan and new queue.
        self.plan = plan
        self.queue = queue

        # Schedule some items.
        self.schedule(now)

    def schedule(self, now=None):
        """
        Schedule items coming up in the next minute.

        It is possible to give a specific current time in order to
        facilitate transition from the current to the incoming plan.
        """

        for item in pop_queue_items(self.queue, now=now):
            self.schedule_item(item)

    def schedule_item(self, data):
        """
        Schedule playback of a specific item.
        """

        # Create the item using the correct class and register it.
        ItemType = Scheduler.ITEM_TYPES[data['type']]
        item = ItemType(self, data['url'])
        self.items.add(item)

        # Put the item actor on the screen and start buffering.
        self.screen.stage.add_child(item.actor)
        item.pause()

        log.msg('Scheduling {0!r}...'.format(item))
        self.add_event(data['start'], item.play)
        self.add_event(data['end'], item.stop)

    def on_item_playing(self, item):
        item.appear()

    def on_item_paused(self, item):
        pass

    def on_item_stopped(self, item):
        pass

    def on_item_appeared(self, item):
        pass

    def on_item_disappeared(self, item):
        self.screen.stage.remove_child(item.actor)
        self.items.discard(item)


def last_midnight():
    """
    Return timestamp of the last midnight.
    """

    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def plan_window(plan, ending_after, starting_before):
    """
    Return list of items in the given window.
    """

    window_items = []

    for item in plan:
        if ending_after < item['end'] and item['start'] < starting_before:
            window_items.append(item)

    return window_items

def pop_queue_items(queue, secs=60, now=None):
    """
    Remove upcoming items from the queue.
    """

    items = []
    if now is None:
        now = time()

    while len(queue) > 0:
        item = queue.pop(0)

        # Discard items already in the past.
        if item['end'] < now:
            continue

        # Stop at items too far in the future.
        if queue[0]['start'] > now + 60:
            queue.insert(0, item)
            break

        # Schedule this item next...
        items.append(item)

    return items


# vim:set sw=4 ts=4 et:
