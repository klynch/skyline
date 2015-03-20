from redis import StrictRedis
from twisted.internet import reactor
from twisted.python import log
import logging
import traceback
import msgpack
import re
import settings
import time

from alerters import trigger_alert
from algorithm_exceptions import *
from algorithms import *


class TooShort(Exception):
    pass


class Stale(Exception):
    pass


class Boring(Exception):
    pass


def analyze_forever(analyzer):
    while reactor.running:
        try:
            analyzer.run()
        except:
            log.err()
    # The writer thread only sleeps when the cache is empty or an error occurs
    time.sleep(1)


def emit(metric, value):
    log.msg(metric + " " + value)


class Analyzer(object):
    def __init__(self, arguments, *args, **kwargs):
        self.args = arguments

    def run(self):
        print "analyzing!"

    def alert(self, metric, results):
        log.msg("alert: " + metric)
        return True
        for alert in settings.ALERTS:
            if re.compile(alert[0]).match(metric):
                try:
                    key = 'skyline:alert:{}:{}'.format(alert[1], metric)
                    if not self.redis_conn.exists(key):
                        self.redis_conn.setex(key, alert[2], time.now())
                        trigger_alert(alert, metric)
                except Exception as e:
                    log.err("could not send alert {} for metric {}: {}".format(alert, metric, e))

    def is_anomalous(self, timeseries, metric_name):
        """
        Filter timeseries and run selected algorithm.
        """
        # Get rid of short series
        if len(timeseries) < settings.MIN_TOLERABLE_LENGTH:
            raise TooShort()

        # Get rid of stale series
        if (time.time() - timeseries[-1][0]) > settings.STALE_PERIOD:
            raise Stale()

        # Get rid of boring series
        if len(set(item[1] for item in timeseries[-settings.MAX_TOLERABLE_BOREDOM:])) == settings.BOREDOM_SET_SIZE:
            raise Boring()

        ensemble = { algorithm: globals()[algorithm](timeseries) for algorithm in settings.ALGORITHMS }

        if ensemble.values().count(True) >= self.args.consensus:
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
        if (new_trigger[1] == trigger_history[-1][1] and
            new_trigger[0] - trigger_history[-1][0] <= 300):
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



class RedisAnalyzer(Analyzer):
    def __init__(self, *args, **kwargs):
        """
        Initialize the Analyzer
        """
        super(RedisAnalyzer, self).__init__(*args, **kwargs)

        #We should not need to reconnect
        log.msg("RedisPublisher connecting to redis: {0}".format(settings.REDIS_OPTS))
        self.redis_conn = StrictRedis(**settings.REDIS_OPTS)
        self.pipe = self.redis_conn.pipeline()

    def waitfor_connection(self):
        while reactor.running:
            try:
                if self.redis_conn.ping():
                    return True
                else:
                    log.err("RedisAnalyzer ping returned false?")
                    time.sleep(10)
            except Exception as e:
                log.err("RedisAnalyzer can't ping redis: {0}".format(e))
                time.sleep(10)

    def run(self):
        while reactor.running:
            self.waitfor_connection()
            # Check existence of a newly updated metic
            metric = self.redis_conn.spop("skyline:metricset:updated")
            if metric:
                self.process(metric)
                #TODO trim metric
            else:
                if int(time.time()) % 60 == 0:
                    log.msg("nothing to do")
                time.sleep(1)
            #TODO send codahale metrics

    def process(self, metric):
        """
        Assign a bunch of metrics for a process to analyze.
        """
        if metric:
            # Fetch the metric metadata and data
            metric_info = self.redis_conn.hgetall("skyline:metric:{0}:info".format(metric))
            metric_data = self.redis_conn.get("skyline:metric:{0}:data".format(metric))
            try:
                packer = msgpack.Unpacker(use_list=False)
                packer.feed(metric_data)
                timeseries = list(packer)
                anomalous, ensemble, datapoint = self.is_anomalous(timeseries, metric)

                # Get the anomaly breakdown - who returned True?
                for algorithm, result in ensemble.iteritems():
                    if result:
                        emit("skyline.analyzer.anomaly.{}".format(algorithm), metric)

                # Update the datastore with the results
                with self.redis_conn.pipeline() as pipe:
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
                    self.alert(metric, ensemble)
                else:
                    emit("skyline.analyzer.metric.ok", metric)

            except (TooShort, Stale, Boring) as e:
                emit("skyline.analyzer.exception.{}".format(e.__class__.__name__), metric)
            except Exception as e:
                emit("skyline.analyzer.exception.Other", metric)
                log.err(e)
