import time
from cache import MetricCache
from twisted.python import log

from regexlist import BlackList, WhiteList


class Publisher(object):
    def __init__(self, api, arguments, *args, **kwargs):
        self.api = api
        self.args = arguments
        BlackList.load(self.api.get_blacklist())
        WhiteList.load(self.api.get_whitelist())

    def run(self):
        "Write datapoints until the MetricCache is completely empty"

        max_age = time.time() - self.args.max_resolution

        while MetricCache:
            dataWritten = False

            self.api.waitfor_connection()

            for metric, datapoints in MetricCache.metrics():
                dataWritten = True

                try:
                    self.api.publish(metric, filter(lambda x: x[0] >= max_age, datapoints))
                except Exception as e:
                    log.err("can't publish {0} to datastore: {1}".format(metric, e))
                    # TODO add metrics back to MetricCache
                    break

            # Avoid churning CPU when only new metrics are in the cache
            if not dataWritten:
                time.sleep(0.1)
