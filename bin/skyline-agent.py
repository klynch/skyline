#!/usr/bin/env python

import argparse
from skyline.api import SkylineRedisApi
from skyline.agents import run_agent
from skyline.utils import check_alert, check_anomalies, check_metric, settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anomaly detection.")
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/" , help="Redis instance to connect to")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Verbose mode")

    subparsers = parser.add_subparsers(title='commands', description='Specify the specific command to run', help='process to run')

    horizon_parser = subparsers.add_parser("horizon", help="Process graphite metrics.")
    horizon_parser.set_defaults(which="horizon")
    horizon_parser.add_argument("--max-resolution", type=int, default=1000, help="The Horizon agent will ignore incoming datapoints if their timestamp is older than MAX_RESOLUTION seconds ago.")
    horizon_parser.add_argument("-i", "--interface", default="", help="Horizon process name")
    horizon_parser.add_argument("-l", "--line-port", type=int, default=0, help="Listen for graphite line data (e.g. 2023)")
    horizon_parser.add_argument("-p", "--pickle-port", type=int, default=0, help="Listen for graphite pickle data (e.g. 2024)")
    horizon_parser.add_argument("-u", "--udp-port", type=int, default=0, help="Listen for graphite udp data (e.g. 2025)")

    analyzer_parser = subparsers.add_parser("analyzer", help="Analyze metrics and detect anomalies.")
    analyzer_parser.set_defaults(which="analyzer")
    analyzer_parser.add_argument("--enable-second-order", action="store_true", default=False, help="This is to enable second order anomalies. (EXPERIMENTAL)")
    analyzer_parser.add_argument("-c", "--consensus", type=int, default=6, help="The number of algorithms that must return True before a metric is classified as anomalous")
    analyzer_parser.add_argument("--full-duration", type=int, default=86400, help="The length of a full timeseries length")
    analyzer_parser.add_argument("--min-tolerable-length", type=int, default=1, help="The minimum length of a timeseries, in datapoints, for the analyzer to recognize it as a complete series")
    analyzer_parser.add_argument("--max-tolerable-boredom", type=int, default=100, help="Sometimes a metric will continually transmit the same number. There's no need to analyze metrics that remain boring like this, so this setting determines the amount of boring datapoints that will be allowed to accumulate before the analyzer skips over the metric. If the metric becomes noisy again, the analyzer will stop ignoring it.")
    analyzer_parser.add_argument("--boredom-set-size", type=int, default=1, help="By default, the analyzer skips a metric if it it has transmitted a single number MAX_TOLERABLE_BOREDOM times. Change this setting if you wish the size of the ignored set to be higher (ie, ignore the metric if there have only been two different values for the past MAX_TOLERABLE_BOREDOM datapoints). This is useful for timeseries that often oscillate between two values.")
    analyzer_parser.add_argument("--stale-period", type=int, default=500, help="The duration, in seconds, for a metric to become 'stale' and for the analyzer to ignore it until new datapoints are added. 'Staleness' means that a datapoint has not been added for STALE_PERIOD seconds")

    roomba_parser = subparsers.add_parser("roomba", help="Cleanup old metric and anomaly data.")
    roomba_parser.set_defaults(which="roomba")
    roomba_parser.add_argument("--full-duration", type=int, default=86400+3600, help="The length of a full timeseries length")
    roomba_parser.add_argument("--clean-timeout", type=int, default=3600, help="This is the amount of extra data to allow")
    roomba_parser.add_argument("--sleep-timeout", type=int, default=3600, help="This is the amount of time roomba will sleep between runs")

    settings_parser = subparsers.add_parser("settings", help="Import and export settings.")
    settings_parser.set_defaults(which="settings")
    settings_parser.add_argument("-i", "--import-file", help="The settings file to import. If an entry is missing from the file, it is set to an emtpy value")

    check_metric_parser = subparsers.add_parser("check_metric", help="Check a metric in skyline.")
    check_metric_parser.set_defaults(which="check_metric")
    check_metric_parser.add_argument("-m", "--metric", required=True, help="the metric to check (e.g. horizon.test.udp)")
    check_metric_parser.add_argument("-i", "--interval", type=int, default=10, help="the metric datapoint interval")

    check_alert_parser = subparsers.add_parser("check_alert", help="Test if an alert would be triggered for a given metric.")
    check_alert_parser.set_defaults(which="check_alert")
    check_alert_parser.add_argument("-m", "--metric", required=True, help="Pass the metric to test")
    check_alert_parser.add_argument("-t", "--trigger", action='store_true', help="Actually trigger the appropriate alerts")

    check_anomalies_parser = subparsers.add_parser("check_anomalies", help="List the anomalies currently in the system.")
    check_anomalies_parser.set_defaults(which="check_anomalies")

    args = parser.parse_args()
    api = SkylineRedisApi(args.redis)

    if args.which == "settings":
        settings(api, args.import_file)
    if args.which == "check_metric":
        check_metric(api, args.metric, args.interval)
    if args.which == "check_alert":
        check_alert(api, args, args.metric, args.trigger)
    if args.which == "check_anomalies":
        check_anomalies(api)
    if args.which in ["horizon", "analyzer", "roomba"]:
        run_agent(api, args.which, args)
