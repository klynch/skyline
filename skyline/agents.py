import sys
import time
from twisted.python import log
from twisted.internet import reactor

def run_forever(agent):
    while reactor.running:
        try:
            agent.run()
        except:
            log.err()
    time.sleep(1)


def horizon_agent(parser, api, args):
    """
    Start the Horizon agent.
    """
    from skyline.horizon.protocols import MetricLineFactory, MetricPickleFactory, MetricDatagramReceiver
    from skyline.horizon.publishers import Publisher

    if not any((args.line_port, args.pickle_port, args.udp_port)):
        parser.error("specify at least one port to listen on")

    if args.line_port:
        reactor.listenTCP(args.line_port, MetricLineFactory(), interface=args.interface)
    if args.pickle_port:
        reactor.listenTCP(args.pickle_port, MetricPickleFactory())
    if args.udp_port:
        reactor.listenUDP(args.udp_port, MetricDatagramReceiver())

    reactor.callInThread(run_forever, Publisher(api, args))


def analyzer_agent(parser, api, args):
    """
    Start the Analyzer agent.
    """
    from skyline.analyzer import check_algorithms
    from skyline.analyzer.analyzer import Analyzer
    check_algorithms(api, args)
    reactor.callInThread(run_forever, Analyzer(api, args))


def roomba_agent(parser, api, args):
    """
    Start the Roomba agent.
    """
    from skyline.roomba import Roomba
    reactor.callInThread(run_forever, Roomba(api, args))


def run_agent(parser, api, which, args):
    """
    Runs a specific agent.
    """
    if which == "horizon":
        horizon_agent(parser, api, args)
    elif which == "analyzer":
        analyzer_agent(parser, api, args)
    elif which == "roomba":
        roomba_agent(parser, api, args)

    log.startLogging(sys.stdout)
    log.msg("Starting {} with the following arguments:".format(args.which))
    for a,v in vars(args).iteritems():
        log.msg("   {0}={1}".format(a, v))

    reactor.run()
