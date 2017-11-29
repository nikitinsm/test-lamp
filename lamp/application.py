import codecs
import json
import time
import struct

import os
from datetime import datetime

from tornado import web, websocket, gen, ioloop
from tornado.iostream import StreamClosedError

from tornado.tcpserver import TCPServer

from lamp.utils import storage, tcp_client


def log(message):
    message = '[{0}] {1}'.format(datetime.now().strftime('%H:%M:%S'), message)
    print(message)


class LampProtocol(object):

    FORMAT = '>ch{value_format}'

    command = dict(
        ON=(b'\x12', 0, None, None),
        OFF=(b'\x13', 0, None, None),
        COLOR=(b'\x20', 3, lambda value: codecs.decode(value, 'hex'), lambda value: codecs.encode(value, 'hex').decode('utf-8')),
    )

    command_reversed = {v[0]: k for k, v in command.items()}

    @staticmethod
    def message(command, value=0):
        command = LampProtocol.command.get(command)
        if not command:
            raise ValueError('Command does not exist')

        command, length, to_bytes, from_bytes = command
        value_format = ''

        if callable(to_bytes):
            value = to_bytes(value)

        if length:
            value_format = '{0}s'.format(length)

        struct_format = LampProtocol.FORMAT.format(value_format=value_format)

        if length:
            result = struct.pack(struct_format, command, length, value)
        else:
            result = struct.pack(struct_format, command, length)
        return result

    @staticmethod
    def process(command, value=None):
        if command not in LampProtocol.command_reversed:
            return None, None

        command_name = LampProtocol.command_reversed[command]
        command, length, to_bytes, from_bytes = LampProtocol.command[command_name]
        if callable(from_bytes):
            value = from_bytes(value)

        return command_name, value


class SocketHandler(websocket.WebSocketHandler):

    def open(self):
        log("WebSocket opened")
        if not storage.websockets:
            storage.websockets = set()
        storage.websockets.add(self)

    def on_message(self, message):
        self.write_message(u"You said: " + message)

    def on_close(self):
        log("WebSocket closed")
        storage.websockets.remove(self)


lamp_client = web.Application([
    (r'/ws', SocketHandler),
    (r'/(.*)', web.StaticFileHandler, {
        'path': os.path.join(os.path.dirname(__file__), "static"),
        'default_filename': 'index.html'
    }),
])


@gen.coroutine
def tcp_client_coroutine():
    """Setup the connection to the echo server and wait for user
    input.
    """
    stream = None
    try:
        stream = yield tcp_client.connect(
            os.environ.get('LAMP_ADDRESS') or '127.0.0.1',
            int(os.environ.get('LAMP_PORT') or 9999)
        )
        log('Connected to Lamp Server')
        ws_message = json.dumps({"command": 'OPEN', "value": ""})
        for ws in storage.websockets or []:
            ws.write_message(ws_message)
        while True:
            value = None
            reply = yield stream.read_bytes(3)
            command, length = struct.unpack('>ch', reply)
            if length:
                value = yield stream.read_bytes(length)
            log([command, length, value])
            command, value = LampProtocol.process(command, value)

            if command:
                ws_message = json.dumps({"command": command, "value": value})
                for ws in storage.websockets or []:
                    ws.write_message(ws_message)

    except Exception as e:
        log(e)
        if stream:
            stream.close()
        ws_message = json.dumps({"command": 'CLOSE', "value": str(e)})
        for ws in storage.websockets or []:
            ws.write_message(ws_message)
        time.sleep(1)
        log('Trying to reconnect to Lamp Server')
        ioloop.IOLoop.current().spawn_callback(tcp_client_coroutine)


#
# LAMP SERVER
# Emulates lamp server behaviour
#


class LampAdminHandler(web.RequestHandler):

    def set_cors(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods'", "OPTIONS, POST")

    def options(self, *args, **kwargs):
        self.set_cors()

    def post(self):
        self.set_cors()
        try:
            message_raw = self.request.body.decode('utf-8')
            log(message_raw)
            message = json.loads(message_raw)
            method = message.get('method')
            params = message.get('params') or {}
            result = json.dumps({'result': getattr(self, 'method_' + method)(**params)})
        except Exception as e:
            result = json.dumps({'error': str(e)})
        self.write(result.encode())

    def method_pingpong(self, **params):
        return params

    def method_message(self, command, value=None):
        """
        Emulates server send client TLV message
        This method transforms json message to TLV and sends it to all active streams
        """
        for stream in storage.lamp_server.get_active_streams():
            message = LampProtocol.message(command, value)
            stream.write(message)

    def method_send_unknown(self):
        for stream in storage.lamp_server.get_active_streams():
            stream.write(b'\xff\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00')


class LampServer(TCPServer):

    _active_streams = None

    def __init__(self, *args, **kwargs):
        super(LampServer, self).__init__(*args, **kwargs)
        self._active_streams = set()

    def get_active_streams(self):
        return self._active_streams

    def create(self, *args, **kwargs):
        return self.listen(9999)

    @gen.coroutine
    def handle_stream(self, stream, address):
        log('Started accepting connections from {0}'.format(address))
        self._active_streams.add(stream)
        while True:
            try:
                yield stream.read_bytes(1)
            except StreamClosedError:
                log('Stopped accepting connections from {0}'.format(address))
                break
        self._active_streams.remove(stream)


lamp_admin = web.Application([
    (r'/', LampAdminHandler),
])
