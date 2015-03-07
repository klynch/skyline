import argparse
import sys
from os.path import dirname, abspath, isdir

import time
from cache import MetricCache

from twisted.application import internet, service
from twisted.internet.protocol import ServerFactory, Protocol

from twisted.python import log
from twisted.internet import reactor
from protocols import *
from publishers import RedisPublisher

# add the shared settings file to namespace
sys.path.insert(0, dirname(dirname(abspath(__file__))))
import settings

def publishForever(publisher):
  while reactor.running:
    try:
      publisher.publishCachedData()
    except:
      log.err()

    time.sleep(1)  # The writer thread only sleeps when the cache is empty or an error occurs


if __name__ == "__main__":
    """
    Start the Horizon agent.
    """
    parser = argparse.ArgumentParser(description='Process graphite metrics.')
    parser.add_argument("-n", "--name", help="Horizon process name")
    parser.add_argument("-i", "--interface", default="", help="Horizon process name")
    parser.add_argument("-l", "--line-port", type=int, default=0, help="Listen for graphite line data (e.g. 2023)")
    parser.add_argument("-p", "--pickle-port", type=int, default=0, help="Listen for graphite pickle data (e.g. 2024)")
    parser.add_argument("-u", "--udp-port", type=int, default=0, help="Listen for graphite udp data (e.g. 2025)")
    args = parser.parse_args()

    if not any((args.line_port, args.pickle_port, args.udp_port)):
        parser.error("specify at least one port to listen on")

    log.startLogging(sys.stdout)

    if args.line_port:
        reactor.listenTCP(args.line_port, MetricLineFactory(), interface=args.interface)
    if args.pickle_port:
        reactor.listenTCP(args.pickle_port, MetricPickleFactory())
    if args.udp_port:
        reactor.listenUDP(args.udp_port, MetricDatagramReceiver())

    reactor.callInThread(publishForever, RedisPublisher())
    reactor.run()
