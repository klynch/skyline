#!/usr/bin/env python

import argparse
import json
import redis
import socket
import time


class NoDataException(Exception):
    pass


def seed_line(args):
    print 'Loading data over line via Horizon...'
    metric = 'horizon.test.line'
    initial = int(time.time()) - args.max_resolution
    with open(args.data, 'r') as f:
        data = json.loads(f.read())
        series = data['results']
        sock = socket.socket()
        sock.connect(("localhost", args.line_port))
        for datapoint in series:
            datapoint[0] = initial
            initial += 1
            sock.sendall("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]))
        sock.close()
    return metric


def seed_udp(args):
    print 'Loading data over udp via Horizon...'
    metric = 'horizon.test.udp'
    initial = int(time.time()) - args.max_resolution
    with open(args.data, 'r') as f:
        data = json.loads(f.read())
        series = data['results']
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for datapoint in series:
            datapoint[0] = initial
            initial += 1
            sock.sendto("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]), ("localhost", args.udp_port))
    return metric


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Seed data.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-d", "--data", required=True, help="seed data file")
    parser.add_argument("--max-resolution", type=int, default=1000, help="The Horizon agent will ignore incoming datapoints if their timestamp is older than MAX_RESOLUTION seconds ago.")
    parser.add_argument("-l", "--line-port", type=int, default=0, help="Listen for graphite line data (e.g. 2023)")
    parser.add_argument("-u", "--udp-port", type=int, default=0, help="Listen for graphite udp data (e.g. 2025)")
    args = parser.parse_args()

    metrics = []
    if args.line_port:
        metrics.append(seed_line(args))
    if args.udp_port:
        metrics.append(seed_udp(args))

    print "Connecting to Redis..."
    r = redis.StrictRedis.from_url(args.redis)

    try:
        members = r.smembers("skyline:metricset:all")
        if members is None:
            raise NoDataException
        for metric in metrics:
            if metric not in members:
                print "Missing metric in set: {0}".format(metric)
                raise NoDataException

            d = r.get("skyline:metric:{0}:data".format(metric))
            if d is None:
                raise NoDataException

            h = r.hgetall("skyline:metric:{0}:info".format(metric))
            if h is None:
                raise NoDataException

        print "Congratulations! The data made it in. The Horizon pipeline seems to be working."
    except NoDataException:
        print "Woops, looks like the metrics didn't make it into Horizon. Try again?"
