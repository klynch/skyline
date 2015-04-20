from twisted.internet import reactor
from twisted.python import log
import collections
import re
import time
import skyline.analyzer.alerts
import skyline.analyzer.algorithms


class TooShort(Exception):
    pass


class Stale(Exception):
    pass


class Boring(Exception):
    pass


def emit(metric, value):
    log.msg(metric + " " + value)


class Analyzer(object):
    def __init__(self, api, arguments, *args, **kwargs):
        self.api = api
        self.args = arguments
        self.alerts_rules = self.api.get_alerts_rules()
        self.alerts_settings = self.api.get_alerts_settings()

    def alert(self, metric, datapoint, ensemble, check=False, trigger=True):
        triggers = []
        for pattern, strategy, timeout, args in self.alerts_rules:
            if re.compile(pattern).match(metric):
                try:
                    # Set the alert with an expiration if it does not exist
                    if not self.api.check_alert(metric, strategy) or check:
                        if not check:
                            self.api.set_alert(metric, strategy, timeout)
                        target = getattr(alerts, 'alert_{0}'.format(strategy))
                        settings = self.alerts_settings.get(strategy, {})
                        if trigger:
                            target(metric, datapoint, ensemble, args, settings)
                        else:
                            triggers.append((strategy, pattern, metric, datapoint, ensemble, args, settings))
                except Exception as e:
                    log.err("could not send alert {} for metric {}: {}".format(strategy, metric, e))
        return triggers

    def is_anomalous(self, timeseries, metric_name):
        """
        Filter timeseries and run selected algorithm.
        """
        # Get rid of short series
        if len(timeseries) < self.args.min_tolerable_length:
            raise TooShort()

        # Get rid of stale series
        if (time.time() - timeseries[-1][0]) > self.args.stale_period:
            raise Stale()

        # Get rid of boring series
        if len(set(item[1] for item in timeseries[-self.args.max_tolerable_boredom:])) == self.args.boredom_set_size:
            raise Boring()

        ensemble = {algorithm: getattr(skyline.analyzer.algorithms, algorithm)(timeseries, self.args) for algorithm in skyline.analyzer.algorithms.ALGORITHMS}

        if collections.Counter(ensemble.values())[True] >= self.args.consensus:
            return True, ensemble, timeseries[-1]

        # Check for second order anomalies
        if self.args.enable_second_order:
            if self.is_anomalously_anomalous(metric_name, ensemble, timeseries[-1]):
                return True, ensemble, timeseries[-1]

        return False, ensemble, timeseries[-1]

    def is_anomalously_anomalous(self, metric_name, ensemble, datapoint):
        """
        This method runs a meta-analysis on the metric to determine whether the
        metric has a past history of triggering. TODO: weight intervals based on datapoint
        """
        # We want the datapoint to avoid triggering twice on the same data
        new_trigger = [time.time(), datapoint[1]]

        # Get the old history
        raw_trigger_history = redis_conn.get('trigger_history:' + metric_name)
        if not raw_trigger_history:
            redis_conn.set('trigger_history:' + metric_name, packb([(time.time(), datapoint[1])]))
            return True

        trigger_history = unpackb(raw_trigger_history)

        # Are we (probably) triggering on the same data?
        if (new_trigger[1] == trigger_history[-1][1] and new_trigger[0] - trigger_history[-1][0] <= 300):
            return False

        # Update the history
        trigger_history.append(new_trigger)
        redis_conn.set('trigger_history.' + metric_name, packb(trigger_history))

        # Should we surface the anomaly?
        trigger_times = [x[0] for x in trigger_history]
        intervals = [
            trigger_times[i + 1] - trigger_times[i]
            for i, v in enumerate(trigger_times)
            if (i + 1) < len(trigger_times)
        ]

        series = pandas.Series(intervals)
        return abs(intervals[-1] - series.mean()) > 3 * series.std()

    def run(self):
        while reactor.running:
            self.api.waitfor_connection()
            # Check existence of a newly updated metic
            metric = self.api.pop_metricset_updated()
            if metric:
                self.process(metric)
                # TODO trim metric
            else:
                if int(time.time()) % 60 == 0:
                    log.msg("nothing to do")
                time.sleep(1)
            # TODO send codahale metrics

    def process(self, metric):
        """
        Assign a bunch of metrics for a process to analyze.
        """
        if metric:
            # Fetch the metric metadata and data
            try:
                timeseries = self.api.get_metric_data(metric)
                anomalous, ensemble, datapoint = self.is_anomalous(timeseries, metric)

                # Get the anomaly breakdown - who returned True?
                for algorithm, result in ensemble.iteritems():
                    if result:
                        emit("skyline.analyzer.anomaly.{}".format(algorithm), metric)

                # Update the datastore with the results
                with self.api.pipeline() as pipe:
                    now = time.time()
                    # Update the anomalous results
                    if anomalous:
                        pipe.zadd("skyline:metricset:anomalous", now, metric)
                        pipe.hset("skyline:metric:{0}:info".format(metric), "last_anomaly_at", now)
                        pipe.hset("skyline:metric:{0}:info".format(metric), "last_anomaly_timestamp", datapoint[0])
                        pipe.hset("skyline:metric:{0}:info".format(metric), "last_anomaly_value", datapoint[1])
                        pipe.hmset("skyline:metric:{0}:last_anomaly_results".format(metric), ensemble)

                    # Update the current results
                    pipe.hset("skyline:metric:{0}:info".format(metric), "is_anomalous", anomalous)
                    pipe.hset("skyline:metric:{0}:info".format(metric), "last_analyzed_at", now)
                    pipe.hset("skyline:metric:{0}:info".format(metric), "last_analyzed_timestamp", datapoint[0])
                    pipe.hset("skyline:metric:{0}:info".format(metric), "last_analyzed_value", datapoint[1])
                    pipe.hmset("skyline:metric:{0}:last_analyzed_results".format(metric), ensemble)
                    pipe.execute()

                # Send out alerts
                if anomalous:
                    emit("skyline.analyzer.metric.anomalous", metric)
                    return self.alert(metric, datapoint, ensemble)
                else:
                    emit("skyline.analyzer.metric.ok", metric)

            except (TooShort, Stale, Boring) as e:
                emit("skyline.analyzer.exception.{}".format(e.__class__.__name__), metric)
            except Exception as e:
                emit("skyline.analyzer.exception.Other", metric)
                log.err(e)
