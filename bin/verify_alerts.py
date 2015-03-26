#!/usr/bin/env python

import argparse
import json
import redis
import time
from skyline.analyzer.analyzer import RedisAnalyzer

parser = argparse.ArgumentParser(description='Analyze metrics for anomalies.')
parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
parser.add_argument("-m", "--metric", default='skyline.horizon.queue_size', help="Pass the metric to test")
parser.add_argument("-t", "--trigger", action='store_true', help="Actually trigger the appropriate alerts")
args = parser.parse_args()

print "Verifying alerts for: {}".format(args.metric)

redis_conn = redis.StrictRedis.from_url(args.redis)

#Check the rules
rules = redis_conn.get("skyline:alerts:rules")
if rules:
    rules = json.loads(rules)
else:
    rules = []
print "rules: {}".format(rules)

#Check the settings
settings = redis_conn.get("skyline:alerts:settings")
if settings:
    settings = json.loads(settings)
else:
    settings = {}
print "settings: {}".format(settings)

a = RedisAnalyzer(args)
for t in a.alert(args.metric, (time.time(), 0), {}, check=True, trigger=args.trigger):
    print t
