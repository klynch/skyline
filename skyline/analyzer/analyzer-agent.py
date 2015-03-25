import argparse
import sys
import traceback
from os.path import dirname, abspath, isdir
import time

from twisted.python import log
from twisted.internet import reactor

from analyzer import analyze_forever, Analyzer, RedisAnalyzer

from algorithms import *

def check_algorithms(args):
    # Make sure we can run all the algorithms
    try:
        log.msg("checking algorithms...")
        timeseries = map(list, zip(map(float, range(int(time.time()) - 86400, int(time.time()) + 1)), xrange(86401)))
        ensemble = Analyzer(args).is_anomalous(timeseries, "dummy")
        log.msg("passed.")
    except KeyError as e:
        log.msg("Algorithm {} deprecated or not defined".format(e))
        sys.exit(1)
    except Exception as e:
        log.msg("Algorithm test run failed.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    """
    Start the Analyzer agent.
    """
    parser = argparse.ArgumentParser(description='Analyze metrics for anomalies.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("--enable-second-order", action="store_true", default=False, help="This is to enable second order anomalies. (EXPERIMENTAL)")
    parser.add_argument("-c", "--consensus", type=int, default=6, help="The number of algorithms that must return True before a metric is classified as anomalous")
    parser.add_argument("--full-duration", type=int, default=86400, help="The length of a full timeseries length")
    parser.add_argument("--min-tolerable-length", type=int, default=1, help="The minimum length of a timeseries, in datapoints, for the analyzer to recognize it as a complete series")
    parser.add_argument("--max-tolerable-boredom", type=int, default=100, help="Sometimes a metric will continually transmit the same number. There's no need to analyze metrics that remain boring like this, so this setting determines the amount of boring datapoints that will be allowed to accumulate before the analyzer skips over the metric. If the metric becomes noisy again, the analyzer will stop ignoring it.")
    parser.add_argument("--boredom-set-size", type=int, default=1, help="By default, the analyzer skips a metric if it it has transmitted a single number MAX_TOLERABLE_BOREDOM times. Change this setting if you wish the size of the ignored set to be higher (ie, ignore the metric if there have only been two different values for the past MAX_TOLERABLE_BOREDOM datapoints). This is useful for timeseries that often oscillate between two values.")
    parser.add_argument("--stale-period", type=int, default=500, help="The duration, in seconds, for a metric to become 'stale' and for the analyzer to ignore it until new datapoints are added. 'Staleness' means that a datapoint has not been added for STALE_PERIOD seconds")
    args = parser.parse_args()

    log.startLogging(sys.stdout)

    log.msg("Starting analyzer with the following arguments:")
    for a,v in vars(args).iteritems():
        log.msg("   {0}={1}".format(a, v))

    check_algorithms(args)

    reactor.callInThread(analyze_forever, RedisAnalyzer(args))
    reactor.run()
