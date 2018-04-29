from threading import Thread, Event
from queue import Empty

import logging
log = logging.getLogger()

class QueuePoller(Thread):

    def __init__(self, queue, callback=None,
                 *args, **kwargs):
        self._stopped = Event()
        self._queue = queue
        self._callback = callback
        super(QueuePoller, self).__init__(*args, **kwargs)

    def join(self, timeout=None):
        self._stopped.set()
        super(QueuePoller, self).join(timeout=timeout)

    def run(self):
        while not self._stopped.is_set():
            try:
                data = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if self._callback:
               self._callback(data)

class OrderExecutor:

    def __init__(self):
        self.is_busy = Event()
        self._reset()

    def _reset(self):
        self.is_busy.clear()
        self.exchange_buy_from = None
        self.exchange_sell_to = None
        self.profit = 0
        self.operate_amount = 0
        self.buy_price = 0
        self.sell_price = 0

    def do_trade(self, exchange_buy_from, exchange_sell_to, amount, buy_price, sell_price):
        if self.is_busy.is_set():
            return
        log.critical('do_trade, %s => %s, %s, %s => %s', exchange_buy_from.name, exchange_sell_to.name, amount, buy_price, sell_price)
        self.is_busy.set()
        self.exchange_buy_from = exchange_buy_from
        self.exchange_sell_to = exchange_sell_to

        self.operate_amount = amount
        self.buy_price = buy_price
        self.sell_price = sell_price

        t = Thread(target=self.do_sell_and_buy)
        t.start()

    def do_sell(self):
        amount = -self.operate_amount
        self.sell_ret = self.exchange_sell_to.new_order(amount, self.sell_price)
        pass

    def do_buy(self):
        amount = self.operate_amount
        self.buy_ret = self.exchange_buy_from.new_order(amount, self.buy_price)
        pass

    def do_sell_and_buy(self):
        log.critical('do_sell_and_buy begin')
        t1 = Thread(target=self.do_sell)
        t2 = Thread(target=self.do_buy)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        log.critical('do_sell_and_buy finish, buy_ret: %s, sell_ret: %s', self.buy_ret, self.sell_ret)
        self._reset()
