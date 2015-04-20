import sys
import time
import traceback
from twisted.python import log

from skyline.analyzer.algorithms import *
from skyline.analyzer.analyzer import Analyzer


def check_algorithms(api, args):
    # Make sure we can run all the algorithms
    try:
        log.msg("checking algorithms...")
        timeseries = map(list, zip(map(float, range(int(time.time()) - 86400, int(time.time()) + 1)), xrange(86401)))
        ensemble = Analyzer(api, args).is_anomalous(timeseries, "dummy")
        log.msg("passed.")
    except KeyError as e:
        log.msg("Algorithm {} deprecated or not defined".format(e))
        sys.exit(1)
    except Exception as e:
        log.msg("Algorithm test run failed.")
        traceback.print_exc()
        sys.exit(1)
