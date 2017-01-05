#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.internet.error import AlreadyCalled
from twisted.internet.task import LoopingCall
from twisted.internet import reactor
from twisted.python import log

from time import time
from datetime import datetime

from telescreen.screen import VideoItem, ImageItem


__all__ = ['Scheduler', 'ItemScheduler']


ITEM_TYPES = {
    'video': VideoItem,
    'image': ImageItem,
}


class Scheduler:
    """
    Facilitates precise task planning and smooth plan transitions.
    """

    def __init__(self):
        # Current plan is only used to detect differences to a new plan.
        self.plan = []

        # Items remaining in the plan to be scheduled later.
        self.queue = []

        # Tasks that are currently running.
        self.tasks = set()

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
        plan.sort(key=lambda task: task['start'])

        # Queue will be modified, plan will stay as it is.
        queue = list(plan)

        # We need to make sure that the plan actually changed before
        # doing anything destructive, such as stopping current playback.
        now = time()
        cur = plan_window(self.plan, now, now + 60)
        new = plan_window(plan, now, now + 60)

        if cur != new:
            log.msg('Resetting schedule...')

            # Stop and get rid of all currently instantiated tasks.
            for task in list(self.tasks):
                self.tasks.discard(task)
                self.stop_task(task)

            # Cancel all pending events.
            for event in list(self.events):
                self.events.discard(event)
                event.cancel()

        else:
            log.msg('Adjusting schedule...')

            # Catch up with the current scheduling.
            self.schedule(now)

            # Work through the new queue up to the same point so that
            # the handoff will go smoothly and tasks won't overlap.
            pop_queue_tasks(queue, now=now)

        # Install new plan and new queue.
        self.plan = plan
        self.queue = queue

        # Schedule some tasks.
        self.schedule(now)

    def schedule(self, now=None):
        """
        Schedule tasks coming up in the next minute.

        It is possible to give a specific current time in order to
        facilitate transition from the current to the incoming plan.
        """

        for task in pop_queue_tasks(self.queue, now=now):
            self.schedule_task(task)

    def schedule_task(self, data):
        """Schedule the scheduler-specific task now."""
        raise NotImplementedError('schedule_task')

    def stop_task(self, task):
        """Stop a running scheduler-specific task."""
        raise NotImplementedError('stop_task')

    def add_task(self, task):
        """Add new running task."""
        self.tasks.add(task)

    def discard_task(self, task):
        """Discard a terminated task."""
        self.tasks.discard(task)


class ItemScheduler (Scheduler):
    def __init__(self, screen):
        super().__init__()

        self.screen = screen

    def schedule_task(self, data):
        """
        Schedule playback of a specific item.
        """

        # Create the item using the correct class and register it.
        ItemType = ITEM_TYPES[data['type']]
        item = ItemType(self, data['url'])
        self.add_task(item)

        # Put the item actor on the screen and start buffering.
        self.screen.stage.add_child(item.actor)
        item.pause()

        log.msg('Scheduling {0!r}...'.format(item))
        self.add_event(data['start'], item.play)
        self.add_event(data['end'], item.stop)

    def stop_task(self, item):
        item.stop()

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
        self.discard_task(item)


def plan_window(plan, ending_after, starting_before):
    """
    Return list of items in the given window.
    """

    window_tasks = []

    for task in plan:
        if ending_after < task['end'] and task['start'] < starting_before:
            window_tasks.append(task)

    return window_tasks

def pop_queue_tasks(queue, secs=60, now=None):
    """
    Remove upcoming items from the queue.
    """

    tasks = []
    if now is None:
        now = time()

    while len(queue) > 0:
        task = queue.pop(0)

        # Discard tasks already in the past.
        if task['end'] < now:
            continue

        # Stop at tasks too far in the future.
        if queue[0]['start'] > now + 60:
            queue.insert(0, task)
            break

        # Schedule this task next...
        tasks.append(task)

    return tasks


# vim:set sw=4 ts=4 et:
