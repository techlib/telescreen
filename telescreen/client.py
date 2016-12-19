#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

import datetime
from txzmq import ZmqFactory, ZmqEndpointType, ZmqEndpoint, ZmqRouterConnection
from twisted.internet import reactor
from twisted.python import log
from uuid import uuid4
from json import loads, dumps
from jsonschema import validate
from telescreen.schema import message_schema
from telescreen.screen import VideoItem, ImageItem, AudioVideoItem
from telescreen.manager import seconds_since_midnight


def make_client(manager, address):
    '''
    Create client with parametres
    Register callbacks
    '''
    zmq_factory = ZmqFactory()
    zmq_endpoint = ZmqEndpoint(ZmqEndpointType.connect, address)

    client = Client(manager, zmq_factory, zmq_endpoint)
    client.registerCallback('ping', client.on_ping)
    client.registerCallback('pong', client.on_pong)
    client.registerCallback('resolution', client.on_resolution)
    client.registerCallback('url', client.on_url)
    client.registerCallback('play', client.on_play)
    client.registerCallback('plan', client.on_plan)
    return client


class Client(ZmqRouterConnection):
    '''
    Client communication enpoint
    '''
    MESSAGE_COUNT = 0
    CLIENT_DICT = {}
    CALLBACK_REGISTER = {}

    def __init__(self, manager, factory, endpoint):
        '''
        Communicate
        '''
        self.manager = manager
        self.last = None

        super(Client, self).__init__(
            factory,
            endpoint,
            identity=manager.machine.encode('utf8')
        )
        self.checkServer()

    def registerCallback(self, action, method):
        if action not in Client.CALLBACK_REGISTER:
            Client.CALLBACK_REGISTER[action] = []

        Client.CALLBACK_REGISTER[action].append(method)

    def unregisterCallback(self, action, method):
        if action in Client.CALLBACK_REGISTER \
                and method in Client.CALLBACK_REGISTER[action]:
            Client.CALLBACK_REGISTER[action].remove(method)

    def checkServer(self):
        '''
        Periodic checking server connection
        '''
        if self.last is None:
            self.init()

        else:
            delta = datetime.datetime.now() - self.last
            if delta.seconds > self.manager.check_interval:
                self.last = None

        if self.last is not None:
            self.status()

        reactor.callLater(self.manager.check_interval, self.checkServer)

    def gotMessage(self, identifier, raw, timestamp):
        '''
        pass
        '''
        Client.MESSAGE_COUNT += 1
        self.last = datetime.datetime.now()
        try:
            message = loads(raw.decode('utf8'))
            validate(message, message_schema)
            id = message['id']

            if 'type' in message \
                    and message['type'] in Client.CALLBACK_REGISTER:
                for method in Client.CALLBACK_REGISTER[message['type']]:
                    method(message, timestamp)
        except Exception as e:
            '''
            Log exception
            '''
            log.err()

    def sendMsg(self, type, message, id=None):
        message['type'] = type
        message['id'] = id or str(uuid4())

        raw = dumps(message).encode('utf8')

        self.sendMultipart(
            b'leader',
            [raw, datetime.datetime.now().isoformat().encode('utf8')]
        )
        return id

    def ok(self, message):
        pass

    def error(self, message, code=None, reply=None):
        pass

    def init(self):
        return self.sendMsg('init', {'device': self.manager.machine})

    def status(self):
        '''
        Send status info. Every check_interval + every file changed
        '''

        if len(self.manager.planner.playing_items) == 0:
            self.manager.poweroff()

        msg = {'status': {
            'power': self.manager.power,
            'type': self.manager.screen.mode,
        }}

        if self.manager.screen.url1:
            msg['status']['urlRight'] = self.manager.screen.url1

        if self.manager.screen.url2:
            msg['status']['urlBottom'] = self.manager.screen.url2

        return self.sendMsg('status', msg)

    def ping(self, id=None):
        return self.sendMsg('ping', {}, id=id)

    def pong(self, id):
        return self.sendMsg('pong', {}, id)

    def on_ping(self, message, timestamp):
        self.pong(message['id'])

    def on_pong(self, message, timestamp):
        '''
        Reaction on pong message
        '''
        pass

    def on_resolution(self, message, timestamp):
        '''
        Change resolution
        '''

        self.manager.screen.setMode(
            message['resolution'].get('type')
        )

        self.manager.screen.setUrl1(
            message['resolution'].get('urlRight')
        )

        self.manager.screen.setUrl2(
            message['resolution'].get('urlBottom')
        )

        self.ok(message)

    def on_url(self, message, timestamp):
        '''
        Set address for Webkit frames
        '''
        if 'urlRight' in message:
            self.manager.screen.right.load_uri(
                message['urlRight']
            )

        if 'urlBottom' in message:
            self.manager.screen.bottom.load_uri(
                message['urlBottom']
            )

        self.ok(message)

    def on_play(self, message, timestamp):
        '''
        Probably for debug
        Add URL to planner. Play from now to midnight
        '''

        log.msg('Receive new play request')
        item = None
        if message['play']['type'] == 'image':
            item = ImageItem(
                self.manager.planner,
                message['play']['uri']
            )

        if message['play']['type'] == 'video':
            item = VideoItem(
                self.manager.planner,
                message['play']['uri']
            )

        if message['play']['type'] == 'audiovideo':
            item = AudioVideoItem(
                self.manager.planner,
                message['play']['uri']
            )

        if item is not None:
            self.manager.planner.schedule_item(
                item,
                seconds_since_midnight()+1,
                86400
            )

        self.ok(message)

    def on_plan(self, message, timestamp):
        '''
        pass
        '''
        log.msg('Receive new plan')
        self.manager.planner.change_plan(message['plan'])
        self.ok(message)

# vim:set sw=4 ts=4 et:
