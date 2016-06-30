import json
import logging
import os
import signal
import socket
import subprocess
import sys
from contextlib import closing
from time import time as now

import colorlog
import eventlet
import pytest

from wampy.constants import DEFAULT_HOST, DEFAULT_PORT
from wampy.networking.connections.wamp import WampConnection

from wampy.exceptions import ConnectionError
from wampy.peers.routers import WampRouter as Router
from wampy.networking.connections.tcp import TCPConnection
from wampy.registry import Registry


logger = logging.getLogger('wampy.testing')

logging_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
}


class ConfigurationError(Exception):
    pass


class PytestConfigurationError(Exception):
    pass


def pytest_configure(config):
    if config.option.logging_level is None:
        logging_level = logging.INFO
    else:
        logging_level = config.option.logging_level
        if logging_level not in logging_level_map:
            raise PytestConfigurationError(
                '{} not a recognised logging level'.format(logging_level)
            )
        logging_level = logging_level_map[logging_level]

    sh = colorlog.StreamHandler()
    sh.setLevel(logging_level)
    formatter = colorlog.ColoredFormatter(
        "%(white)s%(name)s %(reset)s %(log_color)s%"
        "(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
        )

    sh.setFormatter(formatter)
    root = logging.getLogger()
    root.addHandler(sh)


def pytest_addoption(parser):
    parser.addoption(
        '--logging-level',
        type=str,
        action='store',
        dest='logging_level',
        help='configure the logging level',
    )


class Crossbar(Router):
    """ Wrapper around a Crossbar.io router instance described by
    ``Crossbar.config``.

    """

    def __init__(
            self, host, port, config_path, crossbar_directory):

        with open(config_path) as data_file:
            config_data = json.load(data_file)

        self.config = config_data
        self.config_path = config_path
        self.crossbar_directory = crossbar_directory

        realms = self.config['workers'][0]['realms']
        roles = realms[0]['roles']

        super(Crossbar, self).__init__(
            "Crossbar.io", host, port, realms, roles
        )

        self.proc = None

    def _wait_until_ready(self, timeout=7, raise_if_not_ready=True):
        # we're only ready when it's possible to connect to the router
        # over TCP - so let's just try it.
        connection = TCPConnection(host=self.host, port=self.port)
        end = now() + timeout

        ready = False

        while not ready:
            timeout = end - now()
            if timeout < 0:
                if raise_if_not_ready:
                    self.logger.exception('%s unable to connect', self.name)
                    raise ConnectionError(
                        'Failed to connect to router'
                    )
                else:
                    return ready

            try:
                connection.connect()
            except socket.error:
                self.logger.warning('failed to connect')
            else:
                ready = True

        return ready

    def start(self):
        """ Start Crossbar.io in a subprocess.
        """
        # will attempt to connect or start up the router
        crossbar_config_path = self.config_path
        cbdir = self.crossbar_directory

        # starts the process from the root of the test namespace
        cmd = [
            'crossbar', 'start',
            '--cbdir', cbdir,
            '--config', crossbar_config_path,
        ]

        self.proc = subprocess.Popen(cmd, preexec_fn=os.setsid)

        self._wait_until_ready()

        self.logger.info(
            '%s router is up and running with PID "%s"',
            self.name, self.proc.pid
        )

    def stop(self):
        self.logger.info('sending SIGTERM to %s', self.proc.pid)

        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except Exception as exc:
            self.logger.exception(exc)
            self.logger.warning('could not kill process group')

            try:
                self.proc.kill()
            except:
                self.logger.execption('Failed to kill parent')
                sys.exit()
            else:
                self.logger.info('killed parent process instead')

        # let the shutdown happen
        eventlet.sleep(1)
        self.logger.info('crossbar shut down')

        Registry.clear()
        self.logger.info('registry cleared')


def check_socket(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        if sock.connect_ex((host, port)) is None:
            raise ConfigurationError(
                '{}:{} not available - is crossbar already running?'.format(
                    host, port
                )
            )


@pytest.yield_fixture
def router():
    check_socket(DEFAULT_HOST, DEFAULT_PORT)

    crossbar = Crossbar(
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        config_path='./test/crossbar.config.json',
        crossbar_directory='./',
    )

    crossbar.start()

    yield crossbar

    crossbar.stop()


@pytest.fixture
def connection(router):
    connection = WampConnection(host=DEFAULT_HOST, port=DEFAULT_PORT)
    connection.connect()

    assert connection.status == 101  # websocket success status
    assert connection.headers['upgrade'] == 'websocket'

    return connection
