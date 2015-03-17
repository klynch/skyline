import argparse
import sys
import traceback
from os.path import dirname, abspath, isdir
import time

from twisted.python import log
from twisted.internet import reactor

# add the shared settings file to namespace
sys.path.insert(0, dirname(dirname(abspath(__file__))))
import settings

from analyzer import analyze_forever, Analyzer, RedisAnalyzer

from algorithms import *

def check_algorithms():
    # Make sure we can run all the algorithms
    try:
        log.msg("checking algorithms...")
        timeseries = map(list, zip(map(float, range(int(time.time()) - 86400, int(time.time()) + 1)), xrange(86401)))
        ensemble = Analyzer().is_anomalous(timeseries, "dummy")
        log.msg("passed.")
    except KeyError as e:
        log.msg("Algorithm {} deprecated or not defined; check settings.ALGORITHMS".format(e))
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
    args = parser.parse_args()

    log.startLogging(sys.stdout)

    check_algorithms()

    reactor.callInThread(analyze_forever, RedisAnalyzer())
    reactor.run()
