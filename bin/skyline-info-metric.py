#!/usr/bin/env python

import argparse
import msgpack
import redis
import sys
import time


def print_metric_data(redis_conn, metric, interval):
    raw_series = redis_conn.get("skyline:metric:{0}:data".format(metric))
    if raw_series is None:
        print "data not found for {0}".format(args.metric)
        return

    unpacker = msgpack.Unpacker()
    unpacker.feed(raw_series)
    timeseries = list(unpacker)

    length = len(timeseries)
    start = time.ctime(int(timeseries[0][0]))
    end = time.ctime(int(timeseries[-1][0]))
    duration = (float(timeseries[-1][0]) - float(timeseries[0][0]))

    last = int(timeseries[0][0]) - 10
    bad = 0
    missing = 0
    for item in timeseries:
        delta = int(item[0]) - last
        if delta > interval:
            bad += 1
            missing += delta
        last = item[0]

    print "Metric Data"
    print "  Stats for {} (interval={}):".format(metric, interval)
    print "  Start time:         {}".format(start)
    print "  End time:           {}".format(end)
    print "  Duration:           {} hours".format(duration/3600)
    print "  Missing datapoints: {}".format(bad)
    print "  Missing time:       {} seconds".format(missing)
    print "  Datapoints:         {}".format(length)
    print "  Min Datapoint:      {}".format(min(item[1] for item in timeseries))
    print "  Max Datapoint:      {}".format(max(item[1] for item in timeseries))
    print "  Ave Datapoint:      {}".format(sum(item[1] for item in timeseries) / length)


def print_metric_info(redis_conn, metric):
    data = redis_conn.hgetall("skyline:metric:{0}:info".format(metric))
    print "\nMetric Info"
    if data is not None:
        for k,v in data.items():
            print "  {0}: {1}".format(k,v)


def print_metric_last_analyzed_results(redis_conn, metric):
    data = redis_conn.hgetall("skyline:metric:{0}:last_analyzed_results".format(metric))
    print "\nLast Analyzed Results"
    if data is not None:
        for k,v in data.items():
            print "  {0}: {1}".format(k,v)


def print_metric_last_anomaly_results(redis_conn, metric):
    data = redis_conn.hgetall("skyline:metric:{0}:last_anomaly_results".format(metric))
    print "\nLast Anomaly Results"
    if data is not None:
        for k,v in data.items():
            print "  {0}: {1}".format(k,v)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check a metric in Skyline.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-m", "--metric", required=True, help="the metric to check (e.g. horizon.test.udp)")
    parser.add_argument("-i", "--interval", type=int, default=10, help="the metric datapoint interval")
    args = parser.parse_args()
    redis_conn = redis.StrictRedis.from_url(args.redis)
    print_metric_data(redis_conn, args.metric, args.interval)
    print_metric_info(redis_conn, args.metric)
    print_metric_last_analyzed_results(redis_conn, args.metric)
    print_metric_last_anomaly_results(redis_conn, args.metric)
