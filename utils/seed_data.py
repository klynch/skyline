#!/usr/bin/env python

import json
import os
import pickle
import socket
import sys
import time
from os.path import dirname, join, realpath
from multiprocessing import Manager, Process, log_to_stderr
from struct import Struct, pack

import redis
import msgpack

# Get the current working directory of this file.
# http://stackoverflow.com/a/4060259/120999
__location__ = realpath(join(os.getcwd(), dirname(__file__)))

# Add the shared settings file to namespace.
sys.path.insert(0, join(__location__, '..', 'src'))
import settings
from utils import metric_data_key, metric_info_key


class NoDataException(Exception):
    pass


def seed_msgpack():
    print 'Loading data over UDP via Horizon...'
    metric = 'horizon.test.msgpack'
    initial = int(time.time()) - settings.MAX_RESOLUTION

    with open(join(__location__, 'data.json'), 'r') as f:
        data = json.loads(f.read())
        series = data['results']
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        for datapoint in series:
            datapoint[0] = initial
            initial += 1
            packet = msgpack.packb((metric, datapoint))
            sock.sendto(packet, (socket.gethostname(), settings.UDP_PORT))


def seed_line():
    print 'Loading data over line via Horizon...'
    metric = 'horizon.test.line'
    initial = int(time.time()) - settings.MAX_RESOLUTION
    with open(join(__location__, 'data.json'), 'r') as f:
        data = json.loads(f.read())
        series = data['results']
        sock = socket.socket()
        sock.connect(("localhost", 2023))
        for datapoint in series:
            datapoint[0] = initial
            initial += 1
            sock.sendall("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]))
        sock.close()
    return metric


def seed_udp():
    print 'Loading data over udp via Horizon...'
    metric = 'horizon.test.udp'
    initial = int(time.time()) - settings.MAX_RESOLUTION
    with open(join(__location__, 'data.json'), 'r') as f:
        data = json.loads(f.read())
        series = data['results']
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for datapoint in series:
            datapoint[0] = initial
            initial += 1
            sock.sendto("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]), ("localhost", 2025))
    return metric



if __name__ == "__main__":
    metrics = [
        seed_line(),
        seed_udp(),
    ]

    print "Connecting to Redis..."
    r = redis.StrictRedis(**settings.REDIS_OPTS)

    try:
        members = r.smembers(settings.UPDATED_METRIC_SET_KEY)
        if members is None:
            raise NoDataException
        for metric in metrics:
            if metric not in members:
                print "Missing metric in set: {0}".format(metric)
                raise NoDataException

        d = r.get(metric_data_key(metric))
        if d is None:
            raise NoDataException

        h = r.hgetall(metric_info_key(metric))
        if h is None:
            raise NoDataException

        print "Congratulations! The data made it in. The Horizon pipeline seems to be working."

    except NoDataException:
        print "Woops, looks like the metrics didn't make it into Horizon. Try again?"
