import os
import time
from itertools import ifilter
from redis import StrictRedis
from cache import MetricCache
from twisted.python import log
from msgpack import packb
import settings
from twisted.internet import reactor

#1. check if in skip list (record blacklist + whitelist hits)
#2. check if stale data (record number of stale metrics)
#3. record to redis

class RedisPublisher:
    def __init__(self):
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
                    log.msg("RedisPublisher ping return false?")
                    time.sleep(10)
            except Exception as e:
                log.msg("RedisPublisher can't ping redis: {0}".format(e))
                time.sleep(10)


    def publish(self, metric, datapoints):
        key = ':'.join((settings.FULL_NAMESPACE, metric))
        data = ''.join(map(packb, datapoints))
        self.pipe.append(key, data)
        self.pipe.sadd(settings.METRIC_SET_KEY, metric)
        self.pipe.execute()


    def publishCachedData(self):
        "Write datapoints until the MetricCache is completely empty"

        max_age = time.time() - settings.MAX_RESOLUTION

        while MetricCache:
            dataWritten = False

            self.waitfor_connection()

            for metric, datapoints in MetricCache.metrics():
                dataWritten = True

                try:
                    self.publish(metric, ifilter(lambda x: x[0] >= max_age, datapoints))
                except Exception as e:
                    log.err("RedisPublisher can't publish {0} to redis: {1}".format(metric, e))
                    #TODO add metrics back to MetricCache
                    break

            # Avoid churning CPU when only new metrics are in the cache
            if not dataWritten:
                time.sleep(0.1)
