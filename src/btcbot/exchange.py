import abc
from threading import Thread, Event

import logging
log = logging.getLogger()

from btcbot.config import ConfigData

class OrderBook:
    def __init__(self, is_ask=False):
        self.is_ask = is_ask
        self.map = {}

    def remove(self, price):
        if price in self.map:
            del self.map[price]

    def add_or_update(self, price, amount):
        amount = abs(amount)
        self.map[price] = amount

    def to_list(self):
        data = sorted(self.map.items(), reverse=not self.is_ask)
        return data

class Candles:

    def __init__(self):
        self.map = {}

    def update(self, ts, data):
        self.map[ts] = data

    def to_list(self):
        data = sorted(self.map.values())
        return data

class Exchange:
    __metaclass__ = abc.ABCMeta

    def __init__(self, name,
            on_order_update=None,
            on_order_book_update=None,
            on_account_update=None,
            on_candels_update=None,
            *args, **kwargs):

        config_data = ConfigData().get_config();
        exchange_config = config_data['exchange_list'][name]

        self.target_pair = config_data['target_token'] + config_data['curency_token']
        self.target_token = config_data['target_token']
        self.curency_token = config_data['curency_token']

        self.name = name
        self.config = exchange_config
        self.ready = Event()
        self.queue_poller_list = []
        self.asset_list = {}
        self.buy_order_list = {}
        self.sell_order_list = {}
        self.bids_book = OrderBook(False)
        self.asks_book = OrderBook(True)

        self.on_order_update = on_order_update
        self.on_order_book_update = on_order_book_update
        self.on_account_update = on_account_update
        self.on_candels_update = on_candels_update
        self.order_book_ready = Event()

        self.candles = Candles()

    def stat(self):
        buy_price, _ = self.asks_book.to_list()[0]

        data = {}
        data['name'] = self.name
        data['asset_list'] = self.asset_list
        amount_can_buy = self.asset_list[self.curency_token] / buy_price
        data['target_token_amount'] = self.asset_list[self.target_token] + amount_can_buy
        return data

    def run(self):
        thread = Thread(target=self.connect)
        thread.start()
        thread.join()
        self.ready.set()

    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    def update_order_list(self, cid, price, amount, is_sell, remove=False):
        map = self.buy_order_list
        if is_sell:
            map = self.sell_order_list

        if not remove:
            map[cid] = (price, abs(amount))
        else:
            if cid in map:
                del map[cid]

        self.notify_order_book_update()

    def notify_order_book_update(self):
        if not self.order_book_ready.is_set():
            return
        if self.on_order_book_update is not None:
            self.on_order_book_update(self)

    def notify_order_update(self):
        if self.on_order_update is not None:
            self.on_order_update(self)
        log.info('order list update, %s: sell, %s; buy, %s', self.name, self.sell_order_list, self.buy_order_list);

    def notify_account_update(self):
        if self.on_account_update is not None:
            self.on_account_update(self)
        log.info('acount_list update: %s', self.asset_list);

    def dump(self):
        data = {}
        data['name'] = self.name
        data['asks_book'] = self.asks_book.to_list()
        data['bids_book'] = self.bids_book.to_list()
        data['buy_order_list'] = self.buy_order_list
        data['sell_order_list'] = self.sell_order_list
        data['asset_list'] = self.asset_list
        return data

    def get_candles(self):
        return self.candles.to_list()
