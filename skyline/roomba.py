import os
import time
import json
import time
from msgpack import Unpacker, packb
from redis import StrictRedis, WatchError
from twisted.python import log
from twisted.internet import reactor


class Roomba(object):
    """The Roomba is responsible for deleting old data."""
    def __init__(self, args):
        super(Roomba, self).__init__()
        self.redis_conn = StrictRedis.from_url(args.redis)
        self.full_duration = args.full_duration
        self.clean_timeout = args.clean_timeout
        self.sleep_timeout = args.sleep_timeout


    def run(self):
        """Trim metrics that are older than full_duration and purge old metrics."""
        metricset = self.redis_conn.smembers("skyline:metricset:all")
        self.clear_old_anomalies()
        for metric in metricset:
            if reactor.running:
                self.clean(metric)
        if reactor.running:
            time.sleep(self.sleep_timeout)


    def clear_old_anomalies(self):
        """Remove every metric who's last anomaly was over full_duration old."""
        return self.redis_conn.zremrangebyscore("skyline:metricset:anomalous", 0, time.time() - self.full_duration)


    def purge(self, metric):
        """Purge every reference to the metric."""
        log.msg("purging: {}".format(metric))
        with self.redis_conn.pipeline() as pipe:
            keys = ["skyline:metric:{0}:last_anomaly_results",
                    "skyline:metric:{0}:data",
                    "skyline:metric:{0}:last_analyzed_results",
                    "skyline:metric:{0}:info"]
            pipe.srem("skyline:metricset:all", metric)
            pipe.zrem("skyline:metricset:anomalous", metric)
            pipe.delete(*[k.format(metric) for k in keys])
            pipe.execute()
            return True


    def clean(self, metric):
        now = time.time()
        unpacker = Unpacker(use_list=False)
        info_key = "skyline:metric:{0}:info".format(metric)
        data_key = "skyline:metric:{0}:data".format(metric)

        info = self.redis_conn.hgetall(info_key)
        last_updated_at = float(info.get("last_updated_at", 0))
        last_cleaned_at = float(info.get("last_cleaned_at", 0))

        minimum_timestamp = now - self.full_duration

        log.msg("cleaning: {} {} {}".format(metric, last_cleaned_at, now - self.clean_timeout))

        # Check if we can purge the whole metric
        if last_updated_at < minimum_timestamp:
            return self.purge(metric)

        # Check if we can skip the metric
        if int(last_cleaned_at) != 0 and last_cleaned_at > (now - self.clean_timeout):
            return

        with self.redis_conn.pipeline() as pipe:
            while True:
                try:
                    # WATCH the key
                    pipe.watch(data_key)

                    # Everything below NEEDS to happen before another datapoint
                    # comes in. If your data has a very small resolution (<.1s),
                    # this technique may not suit you.
                    raw_series = pipe.get(data_key)
                    unpacker.feed(raw_series)
                    datapoints = sorted([unpacked for unpacked in unpacker])

                    # Put pipe back in multi mode
                    pipe.multi()

                    # Remove old datapoints
                    trimmed = [p for p in datapoints if p[0] > minimum_timestamp]
                    length = len(trimmed)

                    # Serialize and turn key back into not-an-array
                    btrimmed = packb(trimmed)
                    if length < 16:
                        pipe.set(data_key, btrimmed[1:])
                    elif length < 65536:
                        pipe.set(data_key, btrimmed[3:])
                    else:
                        pipe.set(data_key, btrimmed[5:])

                    pipe.hset(info_key, "length", length)
                    pipe.hset(info_key, "last_cleaned_at", now)
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
                    self.purge(metric)
                finally:
                    pipe.reset()
