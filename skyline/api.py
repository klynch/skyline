from redis import StrictRedis
from twisted.internet import reactor
from twisted.python import log
import msgpack
import json
import time


DEFAULT_SETTINGS = [
    ("skyline:config:alerts:rules", []),
    ("skyline:config:alerts:settings", {}),
    ("skyline:config:blacklist", []),
    ("skyline:config:whitelist", []),
    ("skyline:config:graphite", {}),
]


class SkylineRedisApi(object):
    def __init__(self, redis_url, *args, **kwargs):
        """
        Initialize the Redis API
        """
        log.msg("connecting to redis: {0}".format(redis_url))
        self.redis_conn = StrictRedis.from_url(redis_url)
        self.pipe = self.redis_conn.pipeline()


    def pipeline(self):
        return self.redis_conn.pipeline()


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


    def purge(self, metric):
        """Purge every reference to the metric."""
        keys = ["skyline:metric:{0}:last_anomaly_results",
                "skyline:metric:{0}:data",
                "skyline:metric:{0}:last_analyzed_results",
                "skyline:metric:{0}:info"]
        with self.redis_conn.pipeline() as pipe:
            pipe.srem("skyline:metricset:all", metric)
            pipe.zrem("skyline:metricset:anomalous", metric)
            pipe.delete(*[k.format(metric) for k in keys])
            pipe.execute()
            return True


    def publish(self, metric, datapoints):
        #Append the data
        data_key = "skyline:metric:{0}:data".format(metric)
        self.pipe.append(data_key, ''.join(map(msgpack.packb, datapoints)))

        #Update some metadata
        info_key = "skyline:metric:{0}:info".format(metric)
        self.pipe.hincrby(info_key, "length", len(datapoints))
        self.pipe.hset(info_key, "last_updated_at", time.time())

        self.pipe.sadd("skyline:metricset:updated", metric) #Key where the set of recently updated metrics is stored
        self.pipe.sadd("skyline:metricset:all", metric) #Key where the set of all known metrics is stored
        self.pipe.execute()


    def get_metric_info(self, metric, pipe=None):
        if pipe is None:
            pipe = self.redis_conn
        return pipe.hgetall("skyline:metric:{0}:info".format(metric))


    def set_metric_info(self, metric, field, value, pipe=None):
        if pipe is None:
            pipe = self.redis_conn
        pipe.hset("skyline:metric:{0}:info".format(metric), field, value)


    def get_metric_data(self, metric, pipe=None):
        if pipe is None:
            pipe = self.redis_conn
        data = pipe.get("skyline:metric:{0}:data".format(metric))
        if data:
            packer = msgpack.Unpacker(use_list=False)
            packer.feed(data)
            return list(packer)
        return []


    def set_metric_data(self, metric, data, pipe=None):
        if pipe is None:
            pipe = self.redis_conn

        # Serialize and turn key back into not-an-array
        length = len(data)
        bdata = msgpack.packb(data)
        data_key = "skyline:metric:{0}:data".format(metric)
        if length < 16:
            pipe.set(data_key, bdata[1:])
        elif length < 65536:
            pipe.set(data_key, bdata[3:])
        else:
            pipe.set(data_key, bdata[5:])

        # Set the metadata
        pipe.hset(info_key, "length", length)


    def get_last_analyzed_results(self, metric, pipe=None):
        if pipe is None:
            pipe = self.redis_conn
        return pipe.hgetall("skyline:metric:{0}:last_analyzed_results".format(metric))


    def get_last_anomaly_results(self, metric, pipe=None):
        if pipe is None:
            pipe = self.redis_conn
        return pipe.hgetall("skyline:metric:{0}:last_anomaly_results".format(metric))


    def get_metricset_all(self):
        return self.redis_conn.smembers("skyline:metricset:all")


    def pop_metricset_updated(self):
        return self.redis_conn.spop("skyline:metricset:updated")


    def get_anomalies(self, withscores=True):
        return self.redis_conn.zrangebyscore("skyline:metricset:anomalous", 0, int(time.time()), withscores=withscores)


    def clear_old_anomalies(self, max_age):
        """Remove every metric who's last anomaly was over full_duration old."""
        return self.redis_conn.zremrangebyscore("skyline:metricset:anomalous", 0, time.time() - max_age)


    def import_settings(self, settings):
        for key, default in DEFAULT_SETTINGS:
            value = settings.get(key, default)
            self.redis_conn.set(key, json.dumps(value))


    def export_settings(self):
        settings = {}
        for key, default in DEFAULT_SETTINGS:
            settings[key] = default
            value = self.redis_conn.get(key)
            if value is not None:
                settings[key] = json.loads(value)
        return settings


    def get_blacklist(self):
        return json.loads(self.redis_conn.get("skyline:config:blacklist"))


    def get_whitelist(self):
        return json.loads(self.redis_conn.get("skyline:config:whitelist"))


    def get_alerts_rules(self):
        """Parse the alerts rules"""
        ret = self.redis_conn.get('skyline:config:alerts:rules')
        if ret:
            return json.loads(ret)
        return []


    def get_alerts_settings(self):
        """Parse the alerts settings"""
        ret = self.redis_conn.get('skyline:config:alerts:settings')
        if ret:
            return json.loads(ret)
        return {}


    def check_alert(self, metric, strategy):
        return self.redis_conn.exists('skyline:alert:{}:{}'.format(strategy, metric))


    def set_alert(self, metric, strategy, timeout):
        self.redis_conn.setex('skyline:alert:{}:{}'.format(strategy, metric), timeout, time.time())
