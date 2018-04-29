import time
from multiprocessing import Queue
from queue import Empty

from btfxwss import BtfxWssClient
from btfxwss.rest import BitfinexRestAuthClient

from btcbot.data import QueuePoller
from btcbot.exchange import Exchange
from btcbot import utils

import logging
log = logging.getLogger()

class Bitfinex(Exchange):

    NOTIFY_FIELDS = {
        'mts': 0,
        'type': 1,
        'message_id': 2,
        '_1': 3,
        'notify_info': 4,
        'code': 5,
        'status': 6,
        'text': 7,
    }

    ORDER_FIELDS = {
        'id': 0,
        'gid': 1,
        'cid': 2,
        'symbol': 3,
        'mtsCreate': 4,
        'mtsUpdate': 5,
        'amount': 6,
        'amountOrig': 7,
        'type': 8,
        'typePrev': 9,
        'flags': 12,
        'status': 13,
        'price': 16,
        'priceAvg': 17,
        'priceTrailing': 18,
        'priceAuxLimit': 19,
        'notify': 23,
        'hidden': 24,
        'placedId': 25,
    }

    _pending_order_list = {}

    def __init__(self, *args, **kwargs):
        super(Bitfinex, self).__init__('bitfinex', *args, **kwargs)
        key = self.config['api_key']
        secret = self.config['api_secret']
        self.socket_client = BtfxWssClient(key, secret)

        self.rest_client = BitfinexRestAuthClient(key, secret)

    def new_order(self, amount, price):
        type = 'EXCHANGE FOK'
        symbol = 't' + self.target_pair
        cid = int(time.time())
        data = {
            'cid': cid,
            'symbol': symbol,
            'type': type,
            'price_trailing': '',
            'price_aux_limit': '',
            'price': str(price),
            'amount': str(amount),
            'hidden': 0,
            'postonly': 0,
        }
        log.critical('new_order: %s', data)
        self.socket_client.new_order(data)

        queue = Queue()
        self._pending_order_list[cid] = queue
        ret = None
        while True:
            try:
                item = queue.get(timeout=2)
            except Empty:
                continue
            log.critical('new_order status update: %s', item)
            status, payload = item
            status = status.lower()
            if status == 'place_fail':
                ret = item
                break;
            elif status == 'place_success':
                continue
            elif 'executed' in status:
                ret = True
                break;
            elif 'canceled' in status:
                ret = item
                break;
        del self._pending_order_list[cid]
        return ret

    def withdraw(self, token_type, amount, address):
        ret = self.rest_client.withdraw(token_type, amount, address)
        return ret

    def _process_order_book(self, item):
        payload, ts = item
        price, count, amount = payload
        # bids
        book = self.asks_book
        if amount > 0:
            book = self.bids_book

        if count == 0:
            book.remove(price)
        else:
            book.add_or_update(price, amount)
        self.order_book_ready.set()
        self.notify_order_book_update()

    def process_account(self, item):
        log.info('acount: %s', item)
        event, payload, ts = item
        if event == 'ws':
            self._process_assets(payload)
        if event == 'wu':
            self._process_assets([payload])
        if event == 'os':
            self._process_order(payload)
        if event == 'on':
            self._process_order([payload])
        if event == 'oc':
            self._process_order([payload])
        if event == 'ou':
            self._process_order([payload])
        if event == 'n':
            self._process_notification(payload)

    def _process_notification(self, raw):
        raw = utils.map_dict(raw, self.NOTIFY_FIELDS, reverse=True)
        type = raw['type']
        data = raw['notify_info']
        status = raw['status']
        log.info('_process_notification: %s', raw)
        if type == 'on-req':
            order_data = utils.map_dict(data, self.ORDER_FIELDS, reverse=True)
            log.info('_process_notification: %s %s', status, order_data)
            cid = order_data['cid']
            if cid in self._pending_order_list:
                queue = self._pending_order_list[cid]
                if status == 'SUCCESS':
                    queue.put(('place_success', raw))
                else:
                    queue.put(('place_fail', raw))


    def _process_order(self, order_list):
        symbol = 't' + self.target_pair
        for item in order_list:
            data = utils.map_dict(item, self.ORDER_FIELDS, reverse=True)
            log.info('_process_order: %s', data)
            if data['symbol'] != symbol:
                continue
            self._process_single_order(data)

    def _process_single_order(self, data):
        cid = data['cid']
        status = data['status']
        executed = 'EXECUTED' in status
        canceled = 'CANCELED' in status

        self.update_order_list(cid, data['price'], data['amount'], data['amount'] < 0,  executed or canceled)

        if cid in self._pending_order_list:
            self._pending_order_list[cid].put((status, data))

    def _process_assets(self, payload):
        for item in payload:
            self.asset_list[item[1]] = item[2]
        self.notify_account_update()

    def _process_candles(self, payload):
        log.info('_process_candles: %s', payload)
        data, _ts = payload
        ts, *_ = data
        self.candles.update(ts, data)

    def connect(self):

        target_pair = self.target_pair
        socket_client = self.socket_client

        socket_client.start()
        while not socket_client.conn.connected.is_set():
            socket_client.conn.connected.wait(1)

        socket_client.authenticate()
        socket_client.subscribe_to_order_book(target_pair)
        socket_client.subscribe_to_candles(target_pair, '1m')

        self._new_queue_poller(socket_client.books(target_pair), self._process_order_book)
        self._new_queue_poller(socket_client.account, self.process_account)
        self._new_queue_poller(socket_client.candles(target_pair), self._process_candles)

    def _new_queue_poller(self, queue, handler):
        poller = QueuePoller(queue, handler)
        poller.start()
        self.queue_poller_list.append(poller)

    def disconnect(self):

        target_pair = self.target_pair
        socket_client = self.socket_client

        socket_client.unsubscribe_from_order_book(target_pair)
        socket_client.unsubscribe_from_candles(target_pair)
        socket_client.stop()

        for poller in self.queue_poller_list:
            poller.join()
