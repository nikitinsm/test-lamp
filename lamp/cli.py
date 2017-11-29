import signal

import click

from tornado import ioloop
from lamp.application import lamp_client, lamp_admin, tcp_client_coroutine, LampServer, log
from lamp.utils import storage, tcp_client


signal_received = False


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    pass


@cli.command()
@click.pass_context
def client(ctx):
    lamp_client.listen(8888)

    def register_signal(sig, frame):
        global signal_received
        log("%s received, stopping server" % sig)
        tcp_client.close()
        log("TCP client %s closed" % tcp_client)
        signal_received = True

    def stop_on_signal():
        global signal_received
        if signal_received:
            ioloop.IOLoop.current().stop()
            log("IOLoop stopped")

    ioloop.PeriodicCallback(stop_on_signal, 1000).start()
    signal.signal(signal.SIGTERM, register_signal)

    ioloop.IOLoop.current().spawn_callback(tcp_client_coroutine)
    ioloop.IOLoop.current().start()


@cli.command()
@click.pass_context
def server(ctx):
    lamp_server = LampServer()
    lamp_server.listen(9999)
    setattr(storage, 'lamp_server', lamp_server)
    lamp_admin.listen(9000)
    ioloop.IOLoop.current().start()


if __name__ == '__main__':
    cli(obj={})