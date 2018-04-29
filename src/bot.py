import logging
import time
import math
import sys

from btcbot import utils
from btcbot.config import ConfigData
from btcbot.bitfinex import Bitfinex
from btcbot.binance import Binance
from btcbot.data import OrderExecutor

import logging
log = logging.getLogger()

class Bot(metaclass=utils.Singleton):

    def start(self):
        self.bitfinex = Bitfinex(on_order_book_update=self.on_order_book_update)
        self.binance = Binance(on_order_book_update=self.on_order_book_update)
        self.bitfinex.connect()
        self.binance.connect()
        self.order_executor = OrderExecutor()

    def on_order_book_update(self, exchange):
        return
        if not self.bitfinex.order_book_ready.is_set() or not self.binance.order_book_ready.is_set():
                return

        self.try_to_trade(self.binance, self.bitfinex)
        self.try_to_trade(self.bitfinex, self.binance)

    def try_to_trade(self, exchange_buy_from, exchange_sell_to):
        asks = exchange_buy_from.asks_book.to_list()
        bids = exchange_sell_to.bids_book.to_list()

        if not asks or not bids:
            return

        sell_price_ratio = 1 - exchange_sell_to.config['fee']
        buy_price_ratio = 1 + exchange_buy_from.config['fee']

        curency_token = exchange_buy_from.curency_token
        target_token = exchange_buy_from.target_token

        curency_token_has = exchange_buy_from.asset_list[curency_token]
        target_token_has = exchange_sell_to.asset_list[target_token]

        log.debug('determine_profit: %s => %s, %s %s => %s %s: %s %s',
                exchange_buy_from.name, exchange_sell_to.name,
                curency_token, curency_token_has,
                target_token, target_token_has,
                asks[0], bids[0],
                );

        list = []
        for ask in asks:
            buy_price, amount_market_avaiable = ask
            buy_price_cost = buy_price * buy_price_ratio
            amount_can_buy = curency_token_has / buy_price

            can_trade = False
            for bid in bids:
                sell_price, amount_market_require = bid
                sell_price_income = sell_price * sell_price_ratio
                profit_price = sell_price_income - buy_price_cost
                profit_rate = profit_price / buy_price * 100
                can_trade = True
                if profit_price > 0:
                    amounts = (amount_market_avaiable * 0.5, amount_market_require * 0.5, amount_can_buy, target_token_has)
                    amount_can_trade = min(*amounts)
                    amount_can_trade = math.floor(amount_can_trade * 100) / 100.0
                    amount_can_trade = int(amount_can_trade)
                    if amount_can_trade < 1:
                        log.critical('determine_profit: amount_can_trade lower than 0.2: %s => %s, %s %s amount_can_trade: %s %s', exchange_buy_from.name, exchange_sell_to.name, asks[0], bids[0], amount_can_trade, amounts);
                        continue;
                    profit = amount_can_trade * profit_price
                    list.append((amount_can_trade, buy_price, sell_price, profit, (ask, bid, buy_price, buy_price_cost, sell_price, sell_price_income, profit_price, profit_rate, *amounts)))
                else:
                    break
            if not can_trade:
                break

        if list:
            log.critical('determine_profit_list: %s => %s, %s %s %s', exchange_buy_from.name, exchange_sell_to.name, asks[0], bids[0], list);

        if not list:
            return
        if self.order_executor.is_busy.is_set():
            log.critical('determine_profit: order_executor is busy')
            return
        list.sort(key=lambda tup: tup[0])
        log.critical('determine_profit: %s %s', exchange_buy_from, exchange_sell_to)
        operate_amount, buy_price, sell_price, *_ = list[0]
        self.order_executor.do_trade(exchange_buy_from, exchange_sell_to, operate_amount, buy_price, sell_price)

    def test_trade(self):
        exchange_buy_from = self.binance
        exchange_sell_to = self.bitfinex
        operate_amount = 0.2
        buy_price = exchange_buy_from.asks_book.to_list()[0][0]
        sell_price = exchange_sell_to.bids_book.to_list()[0][0]
        self.order_executor.do_trade(exchange_buy_from, exchange_sell_to, operate_amount, buy_price, sell_price)

    def stop(self):
        self.bitfinex.disconnect()
        self.binance.disconnect()

    def stat(self):

        data = {}
        data['binance'] = self.binance.stat()
        data['bitfinex'] = self.bitfinex.stat()
        return data
