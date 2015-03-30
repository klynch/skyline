#!/usr/bin/env python

import argparse
import sys
from twisted.python import log
from twisted.internet import reactor

from skyline.roomba import Roomba

def roomba_forever(roomba):
  while reactor.running:
    try:
      roomba.run()
    except:
      log.err()


if __name__ == "__main__":
    """
    Start the Roomba.
    """
    parser = argparse.ArgumentParser(description='Analyze metrics for anomalies.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("--full-duration", type=int, default=86400+3600, help="The length of a full timeseries length")
    parser.add_argument("--clean-timeout", type=int, default=3600, help="This is the amount of extra data to allow")
    args = parser.parse_args()

    log.startLogging(sys.stdout)

    log.msg("Starting roomba with the following arguments:")
    for a,v in vars(args).iteritems():
        log.msg("   {0}={1}".format(a, v))

    reactor.callInThread(roomba_forever, Roomba(args))
    reactor.run()
