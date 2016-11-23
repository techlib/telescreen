# -*- coding: utf-8 -*-
import datetime
from txzmq import ZmqFactory, ZmqEndpointType, ZmqEndpoint, ZmqRouterConnection
from twisted.internet import reactor
from uuid import uuid4
from json import loads, dumps
from jsonschema import validate
from telescreen.schema import schema
from telescreen.screen import VideoItem, ImageItem
from telescreen.manager import seconds_since_midnight


def make_client(manager, address):
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
    MESSAGE_COUNT = 0
    CLIENT_DICT = {}
    CALLBACK_REGISTER = {}

    def __init__(self, manager, factory, endpoint):
        self.manager = manager
        self._init = None

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
        self.ping()
        if self._init is None:
            self.init()

        reactor.callLater(300, self.checkServer)

    def gotMessage(self, identifier, raw, timestamp):
        '''
        pass
        '''
        Client.MESSAGE_COUNT += 1
        try:
            message = loads(raw.decode('utf8'))
            validate(message, schema)
            id = message['id']

            if self._init == id:
                self._init = True

            if 'type' in message \
                    and message['type'] in Client.CALLBACK_REGISTER:
                for method in Client.CALLBACK_REGISTER[message['type']]:
                    method(message, timestamp)
        except Exception as e:
            '''
            Log exception
            '''
            print("Exception", e)

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
        print("INIT")
        return self.sendMsg('init', {'device': self.manager.machine})

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

        # Fit screen
        if message['resolution']['type'] == 'fullscreen':
            self.manager.screen.mode = self.manager.screen.MODE_FULLSCREEN

        elif message['resolution']['type'] == 'right':
            self.manager.screen.mode = self.manager.screen.MODE_RIGHT

        elif message['resolution']['type'] == 'both':
            self.manager.screen.mode = self.manager.screen.MODE_BOTH

        # Set url address
        if 'urlRight' in message['resolution']:
            self.manager.screen.right.load_uri(
                message['resolution']['urlRight']
            )

        if 'urlBottom' in message['resolution']:
            self.manager.screen.bottom.load_uri(
                message['resolution']['urlBottom']
            )

        self.manager.screen.on_resize(
            self.manager.screen
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
        Add USL to planner. Play from no to midnight
        '''
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

        if item is not None:
            self.manager.planner.schedule_item(
                item,
                seconds_since_midnight()+1,
                86400
            )

    def on_plan(self, message, timestamp):
        '''
        pass
        '''
        print(message)
        self.manager.planner.change_plan(message['plan'])
        #now = seconds_since_midnight()
        #fib = 0
        #for plan in message['plan']:
            #if plan['start'] < now:
                #continue

            #item = None
            #if plan['type'] == 'image':
                #item = ImageItem(
                    #self.manager.planner,
                    #plan['uri']
                #)

            #if plan['type'] == 'video':
                #item = VideoItem(
                    #self.manager.planner,
                    #plan['uri']
                #)

            #if item is not None:
                #self.manager.planner.schedule_item(
                    #item,
                    #plan['start'],
                    #plan['end']
                #)

            #fib += 1

            #if fib == 3:
                #break

