import os
import time
import json
from redis import StrictRedis
from cache import MetricCache
from twisted.python import log
from msgpack import packb
from twisted.internet import reactor

#1. check if in skip list (record blacklist + whitelist hits)
#2. check if stale data (record number of stale metrics)
#3. record to redis

from regexlist import BlackList, WhiteList

def publish_forever(publisher):
  while reactor.running:
    try:
      publisher.publishCachedData()
    except:
      log.err()
    # The writer thread only sleeps when the cache is empty or an error occurs
    time.sleep(1)


class Publisher(object):
    def __init__(self, arguments, *args, **kwargs):
        self.args = arguments


class RedisPublisher(Publisher):
    def __init__(self, *args, **kwargs):
        """
        Initialize the Publisher
        """
        super(RedisPublisher, self).__init__(*args, **kwargs)

        #We should not need to reconnect
        log.msg("RedisPublisher connecting to redis: {0}".format(self.args.redis))
        self.redis_conn = StrictRedis.from_url(self.args.redis)
        self.pipe = self.redis_conn.pipeline()
        BlackList.load(json.loads(self.redis_conn.get("skyline:config:blacklist")))
        WhiteList.load(json.loads(self.redis_conn.get("skyline:config:whitelist")))


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
        #Append the data
        data_key = "skyline:metric:{0}:data".format(metric)
        self.pipe.append(data_key, ''.join(map(packb, datapoints)))

        #Update some metadata
        info_key = "skyline:metric:{0}:info".format(metric)
        self.pipe.hincrby(info_key, "length", len(datapoints))
        self.pipe.hset(info_key, "last_updated_at", time.time())

        self.pipe.sadd("skyline:metricset:updated", metric) #Key where the set of recently updated metrics is stored
        self.pipe.sadd("skyline:metricset:all", metric) #Key where the set of all known metrics is stored
        self.pipe.execute()


    def publishCachedData(self):
        "Write datapoints until the MetricCache is completely empty"

        max_age = time.time() - self.args.max_resolution

        while MetricCache:
            dataWritten = False

            self.waitfor_connection()

            for metric, datapoints in MetricCache.metrics():
                dataWritten = True

                try:
                    self.publish(metric, filter(lambda x: x[0] >= max_age, datapoints))
                except Exception as e:
                    log.err("RedisPublisher can't publish {0} to redis: {1}".format(metric, e))
                    #TODO add metrics back to MetricCache
                    break

            # Avoid churning CPU when only new metrics are in the cache
            if not dataWritten:
                time.sleep(0.1)
