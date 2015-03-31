#!/usr/bin/env python

import argparse
import msgpack
import redis
import sys
import time


def print_anomalous(redis_conn, metric=None, withscores=True):
    anomalous = redis_conn.zrangebyscore("skyline:metricset:anomalous", 0, int(time.time()), withscores=withscores)
    for anomaly in anomalous:
        if isinstance(anomaly, (list, tuple)):
            print "{0}\t{1}".format(time.ctime(anomaly[1]), anomaly[0])
        else:
            print "{0}".format(anomaly[0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check a metric in Skyline.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-m", "--metric", default=None, help="the metric to check (e.g. horizon.test.udp)")
    args = parser.parse_args()
    redis_conn = redis.StrictRedis.from_url(args.redis)
    print_anomalous(redis_conn, args.metric)
