class API:

    method_list = ['test_buy', 'test_sell']

    def __init__(self, bot):
        self.bot = bot

    def dispatch_reqeust(self, exchange_name, exchange_method_name):
        exchange_instance = getattr(self.bot, exchange_name)

        if exchange_method_name in self.method_list:
            api_method = getattr(self, exchange_method_name)
            data = api_method(exchange_instance)
        else:
            exchange_attr = getattr(exchange_instance, exchange_method_name)
            if callable(exchange_attr):
                data = exchange_attr()
            else:
                data = exchange_attr
        return data

    def test_buy(exchange):
        asks = exchange.asks_book.to_list()
        price, amount = asks[0]
        ret = exchange.new_order(0.2, price)
        return ret

    def test_sell(exchange):
        bids = exchange.bids_book.to_list()
        price, amount = bids[0]
        ret = exchange.new_order(-0.2, price)
        return ret
