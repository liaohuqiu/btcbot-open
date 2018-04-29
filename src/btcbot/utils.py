import os
import logging
import logging.handlers
import json
import sys
import yaml
from jinja2 import Environment
from cubi import logger

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

def map_dict(data_src, keys, reverse=False):
    data = {}
    for key_from, key_to in keys.items():
        if reverse:
            data[key_from] = data_src[key_to]
        else:
            data[key_to] = data_src[key_from]
    return data

def load_json(file):
    data = None
    with open(file, 'r') as f:
        data = json.load(f)
    return data

def dump_json(data, file):
    with open(file, 'w') as outfile:
        json.dump(data, outfile)

def load_yaml(file):
    data = None
    if not os.path.isfile(file):
        return data
    with open(file, 'r') as f:
        data = yaml.load(f)
    return data

def dump_yaml(data, file):
    with open(file, 'w') as outfile:
        yaml.safe_dump(data, outfile, default_flow_style=False)

def json_to_yaml(src, out):
    data = load_json(src)
    dump_yaml(data, out)

def load_config(config_name):
    if not config_name:
        config_name = os.path.basename(sys.argv[1])
    current_dir = os.path.dirname(os.path.realpath(__file__))
    root_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(root_dir)
    file_name = root_dir + '/config/' + config_name
    name, ext = os.path.splitext(file_name)

    if ext == '.json':
        return load_json(file_name)
    elif ext == '.yml' or ext == '.yaml':
        return load_yaml(file_name)
    return None

def render_str(patten, data):
    env = Environment(keep_trailing_newline=True)
    patten = patten.decode('utf-8')
    s = env.from_string(patten)
    ret = s.render(data)
    return ret

def render_template_file_to_file(template_file, data, target_file):
    if not os.path.isfile(template_file):
        return
    ensure_dir_for_file(target_file)
    with open(target_file, 'w') as fw:
        fw.write(render_template_file(template_file, data))

def render_template_file(template_file, data):
    if not os.path.isfile(template_file):
        return
    result = ''
    with open(template_file, 'r') as f:
        patten = f.read()
        result = render_str(patten, data)
    return result

def ensure_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def ensure_dir_for_file(file):
    ensure_dir(os.path.dirname(file))

def make_logger(config):
    # log_level
    log_level = logging.INFO
    if 'log_level' in config:
        level = config['log_level'].lower()
        log_level_conf = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'warn': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL,
        }
        if level in log_level_conf:
            log_level = log_level_conf[level]

    formatter = logging.Formatter(config['app_name'] + '_' + config['env'] + ': %(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s')

    handlers = []
    if 'syslog_ng_server' in config:
        syslog_handler = logging.handlers.SysLogHandler(address=(config['syslog_ng_server'], 514), facility='local6')
        syslog_handler.setFormatter(formatter)
        syslog_handler.setLevel(log_level)
        syslog_handler.setLevel(logging.DEBUG)
        handlers.append(syslog_handler)

    if 'debug' in config and config['debug']:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(log_level)
        handlers.append(stream_handler)

    if handlers:
        logging.basicConfig(level=logging.DEBUG, handlers=handlers)
