from btcbot.config import ConfigData
from btcbot import utils
from bot import Bot
import sys
import signal

config = utils.load_config('app.yml')
ConfigData().init(config)
utils.make_logger(config)

_bot = Bot()
def signal_handler(signal, frame):
    _bot.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
_bot.start()
