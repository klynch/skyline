#!/usr/bin/env python

import argparse
import time
from skyline.api import SkylineRedisApi
from skyline.analyzer.analyzer import Analyzer


def check_alert(api, args, metric, trigger):
    print "Verifying alerts for: {}".format(metric)

    print "rules: {}".format(api.get_alerts_rules())
    print "settings: {}".format(api.get_alerts_settings())

    a = Analyzer(api, args)
    for t in a.alert(metric, (time.time(), 0), {}, check=True, trigger=trigger):
        print t


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze metrics for anomalies.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-m", "--metric", required=True, help="Pass the metric to test")
    parser.add_argument("-t", "--trigger", action='store_true', help="Actually trigger the appropriate alerts")
    args = parser.parse_args()
    api = SkylineRedisApi(args.redis)
    check_alert(api, args, args.metric, args.trigger)
