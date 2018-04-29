from btcbot import utils

class ConfigData(metaclass=utils.Singleton):

    def init(self, config):
        self._data = config
        pass

    def get_config(self):
        return self._data
