import time
from threading import Thread, Event, Timer

from binance.client import Client as BinanceClient
from binance.websockets import BinanceSocketManager

from multiprocessing import Queue
from btcbot import utils
from btcbot.data import QueuePoller
from btcbot.exchange import Exchange

import logging
log = logging.getLogger()

class Binance(Exchange):

    ORDER_KEYS_MAP = {
            's': 'symbol',
            'X': 'status',
            'i': 'orderId',
            'p': 'price',
            'q': 'origQty',
            'S': 'side',
            }

    def __init__(self, *args, **kwargs):
        super(Binance, self).__init__('binance', *args, **kwargs)

        key = self.config['api_key']
        secret = self.config['api_secret']

        self.client = BinanceClient(key, secret)
        self._debpth_data_buffer = Queue()
        self._load_depth_snapshot_thread = None

    def new_order(self, amount, price):
        type = 'LIMIT'
        side = 'BUY' if amount > 0 else 'SELL'
        data = {
            'price': price,
            'quantity': abs(amount),
            'symbol': self.target_pair,
            'timeInForce': 'FOK',
            'side': side,
            'type': type,
        }
        log.critical('new_order: %s', data)
        ret = self.client.create_order(**data)
        log.critical('new_order: %s', ret)
        if ret['status'] == 'FILLED':
            return True
        else:
            return ret

    def withdraw(self, token_type, amount, address):
        ret = self.client.withdraw(token_type, amount, address)
        return ret

    def _update_order_book_list(self, book, list):
        for item in list:
            price, amount, _ = item
            price = float(price)
            amount = float(amount)
            if amount == 0:
                book.remove(price)
            else:
                book.add_or_update(price, amount)

    def _update_order_book(self, bid_list, ask_list):
        log.debug('_update_order_book')
        self._update_order_book_list(self.bids_book, bid_list)
        self._update_order_book_list(self.asks_book, ask_list)

        self.notify_order_book_update()

    def _process_order(self, data, keys=None):
        if keys is not None:
            data = utils.map_dict(data, keys)
        symbol = data['symbol']
        if symbol != self.target_pair:
            return
        status = data['status']
        remove = status in 'CANCELED FILLED EXPIRED CANCELED'
        self.update_order_list(data['orderId'], float(data['price']), float(data['origQty']), data['side'] == 'SELL', remove)

    def _process_assets(self, balances, keys=None):
        for item in balances:
            if keys is not None:
                item = utils.map_dict(item, keys)
            free_amount_str = item['free']
            if free_amount_str == '0.00000000':
                continue
            free_amount = float(free_amount_str)
            self.asset_list[item['asset']] = free_amount
        self.notify_account_update()

    def connect(self):
        self._load_init_data()
        self._new_queue_poller(self.client.queue, self.process_message)
        self.client.start_depth_socket(self.target_pair)
        self.client.start_user_socket()

    def _load_init_data(self):
        open_orders = self.client.get_open_orders()
        for open_order in open_orders:
            self._process_order(open_order)
        log.info('_load_init_data, open_orders: %s', open_orders)

        my_account = self.client.get_account()
        log.info('_load_init_data, my_account: %s', my_account)
        self._process_assets(my_account['balances'])

    def _load_depth_data(self):
        depth_data = self.client.get_order_book(symbol=self.target_pair)
        log.info('_load_init_data, depth_data: %s', depth_data)
        last_update_id = depth_data['lastUpdateId'];
        self._update_order_book(depth_data['bids'], depth_data['asks'])
        while not self._debpth_data_buffer.empty():
            item = self._debpth_data_buffer.get()
            if item['u'] <= last_update_id:
                log.info('_load_init_data, skip: %s', item)
                continue
            else:
                self._update_order_book(item['b'], item['a'])
        self.order_book_ready.set()
        log.info('_load_depth_data finish');

    def _new_queue_poller(self, queue, handler):
        poller = QueuePoller(queue, handler)
        poller.start()
        self.queue_poller_list.append(poller)

    def process_message(self, msg):
        log.debug('process_message: %s', msg)
        payload, ts = msg
        event = payload['e']
        if event == 'executionReport':
            self._process_order(payload, self.ORDER_KEYS_MAP)
        if event == 'outboundAccountInfo':
            self._process_assets(payload['B'], {'f': 'free', 'a': 'asset'})
        if event == 'depthUpdate':
            if self.order_book_ready.is_set():
                self._update_order_book(payload['b'], payload['a'])
            else:
                self._debpth_data_buffer.put(payload)
                if self._debpth_data_buffer.qsize() >= 2 and self._load_depth_snapshot_thread is None:
                    self._load_depth_snapshot_thread = Thread(target=self._load_depth_data)
                    self._load_depth_snapshot_thread.start()

    def disconnect(self):
        self.client.close()

        for poller in self.queue_poller_list:
            poller.join()

