#!/usr/bin/env python

import argparse
import json
import redis
import time
from skyline.analyzer.analyzer import RedisAnalyzer


def check_alert(redis_conn, args, metric, trigger):
    print "Verifying alerts for: {}".format(metric)

    #Check the rules
    rules = json.loads(redis_conn.get("skyline:config:alerts:rules"))
    print "rules: {}".format(rules)

    #Check the settings
    settings = json.loads(redis_conn.get("skyline:config:alerts:settings"))
    print "settings: {}".format(settings)

    a = RedisAnalyzer(args)
    for t in a.alert(metric, (time.time(), 0), {}, check=True, trigger=trigger):
        print t


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze metrics for anomalies.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-m", "--metric", required=True, help="Pass the metric to test")
    parser.add_argument("-t", "--trigger", action='store_true', help="Actually trigger the appropriate alerts")
    args = parser.parse_args()
    check_alert(redis.StrictRedis.from_url(args.redis), args, args.metric, args.trigger)
