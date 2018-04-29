# Import Built-Ins
import logging
import json
import time
import ssl
import hashlib
import hmac
from threading import Thread, Event, Timer

import websocket

log = logging.getLogger(__name__)

class WebSocketConnection(Thread):

    def __init__(self, queue, url, *args, timeout=None, sslopt=None,
                 http_proxy_host=None, http_proxy_port=None, http_proxy_auth=None, http_no_proxy=None,
                 reconnect_interval=None, **kwargs):

        self.queue = queue
        self.url = url

        # Connection Settings
        self.socket = None
        self.sslopt = sslopt if sslopt else {}

        # Proxy Settings
        self.http_proxy_host = http_proxy_host
        self.http_proxy_port = http_proxy_port
        self.http_proxy_auth = http_proxy_auth
        self.http_no_proxy = http_no_proxy

        # Connection Handling Attributes
        self.is_connected = Event()
        self.disconnect_called = Event()
        self.reconnect_required = Event()
        self.reconnect_interval = reconnect_interval if reconnect_interval else 10

        # Tracks Websocket Connection
        self.connection_timeout_timer = None
        self.connection_timeout = timeout if timeout else 30

        # Call init of Thread and pass remaining args and kwargs
        Thread.__init__(self)
        self.daemon = True

    def disconnect(self):
        log.debug("disconnect()")
        self.reconnect_required.clear()
        self.disconnect_called.set()
        if self.socket:
            self.socket.close()
        self.join(timeout=1)

    def reconnect(self):
        log.debug("reconnect()")
        self.is_connected.clear()
        self.reconnect_required.set()
        if self.socket:
            self.socket.close()

    def run(self):
        self.socket = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        if 'ca_certs' not in self.sslopt.keys():
            ssl_defaults = ssl.get_default_verify_paths()
            self.sslopt['ca_certs'] = ssl_defaults.cafile

        log.debug('connect to: %s', self.url)
        self._start_connection_timeout()
        self._connect()

        while self.reconnect_required.is_set():
            if not self.disconnect_called.is_set():
                log.info('Attempting to connect again in %s seconds: %s', self.reconnect_interval, self.url)
                time.sleep(self.reconnect_interval)
                self._connect()


    def _connect(self):
        # We need to set this flag since closing the socket will
        # set it to False
        self.socket.keep_running = True
        self.socket.run_forever(sslopt=self.sslopt,
                        http_proxy_host=self.http_proxy_host,
                        http_proxy_port=self.http_proxy_port,
                        http_proxy_auth=self.http_proxy_auth,
                        http_no_proxy=self.http_no_proxy)


    def _on_message(self, ws, message):
        raw, received_at = message, time.time()
        log.debug("_on_message(): Received new message %s at %s",
                       raw, received_at)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Something wrong with this data, log and discard
            return

        self.queue.put((data, received_at))

    def _on_close(self, ws, *args):
        log.info("Connection closed")
        self.is_connected.clear()
        self._stop_connection_timeout_timer()

    def _on_open(self, ws):
        log.info("Connection opened")
        self.is_connected.set()
        self._stop_connection_timeout_timer()
        if self.reconnect_required.is_set():
            log.info("_on_open(): Connection re_connected")

    def _on_error(self, ws, error):
        log.info("Connection Error - %s", error)
        self.reconnect_required.set()
        self.is_connected.clear()

    def _stop_connection_timeout_timer(self):
        if self.connection_timeout_timer:
            log.debug('_stop_connection_timeout_timer()')
            self.connection_timeout_timer.cancel()

    def _start_connection_timeout(self):
        log.debug('_start_connection_timeout()')
        self.connection_timeout_timer = Timer(self.connection_timeout, self._connection_timed_out)
        self.connection_timeout_timer.start()

    def _connection_timed_out(self):
        log.debug('_connection_timed_out()')
        self.reconnect()
