import threading

from tornado.tcpclient import TCPClient


tcp_client = TCPClient()


storage = threading.local()


storage.websockets = None
storage.lamp_server = None