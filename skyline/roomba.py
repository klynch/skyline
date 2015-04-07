import os
import time
import time
from redis import WatchError
from twisted.python import log
from twisted.internet import reactor


class Roomba(object):
    """The Roomba is responsible for deleting old data."""
    def __init__(self, api, args):
        self.api = api
        self.full_duration = args.full_duration
        self.clean_timeout = args.clean_timeout
        self.sleep_timeout = args.sleep_timeout
        self.sleep_period = 5

    def run(self):
        """Trim metrics that are older than full_duration and purge old metrics."""
        self.api.clear_old_anomalies(self.full_duration)
        for metric in self.api.get_metricset_all():
            if reactor.running:
                self.clean(metric)
        if reactor.running:
            if self.sleep_timeout < self.sleep_period:
                time.sleep(self.sleep_timeout)
            else:
                for i in xrange(self.sleep_timeout / self.sleep_period):
                    time.sleep(self.sleep_period)
                    if not reactor.running:
                        return

    def clean(self, metric):
        now = time.time()
        info = self.api.get_metric_info(metric)
        last_updated_at = float(info.get("last_updated_at", 0))
        last_cleaned_at = float(info.get("last_cleaned_at", 0))

        minimum_timestamp = now - self.full_duration

        log.msg("cleaning: {} {} {}".format(metric, last_cleaned_at, now - self.clean_timeout))

        # Check if we can purge the whole metric
        if last_updated_at < minimum_timestamp:
            log.msg("purging old metric: {}".format(metric))
            return self.api.purge(metric)

        # Check if we can skip the metric
        if int(last_cleaned_at) != 0 and last_cleaned_at > (now - self.clean_timeout):
            return

        with self.api.pipeline() as pipe:
            while True:
                try:
                    # WATCH the key
                    pipe.watch("skyline:metric:{0}:data".format(metric))

                    # Everything below NEEDS to happen before another datapoint
                    # comes in. If your data has a very small resolution (<.1s),
                    # this technique may not suit you.
                    datapoints = self.api.get_metric_data(metric, pipe)

                    # Put pipe back in multi mode
                    pipe.multi()

                    # Remove old datapoints
                    trimmed = [p for p in datapoints if p[0] > minimum_timestamp]
                    self.api.set_metric_data(metric, trimmed, pipe)

                    # Finalize processing
                    self.api.set_metric_info(metric, "last_cleaned_at", now)
                    pipe.execute()

                    log.msg('operated on {} in {} seconds'.format(metric, time.time() - now))
                    return

                except WatchError:
                    log.msg("blocked: {}".format(metric))
                    continue
                    self.blocked += 1
                except Exception as e:
                    # If something bad happens, zap the key and hope it goes away
                    log.msg(e)
                    log.msg("purging bad metric: {}".format(metric))
                    self.api.purge(metric)
                finally:
                    pipe.reset()
