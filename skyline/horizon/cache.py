"""Copyright 2009 Chris Davis

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

from threading import Lock
from twisted.python import log


class MetricCache(dict):
    def __init__(self, max_size=None):
        self.size = 0
        self.lock = Lock()
        self.max_size = max_size

    def __setitem__(self, key, value):
        raise TypeError("Use store() method instead!")

    def store(self, metric, datapoint):
        with self.lock:
            self.setdefault(metric, []).append(datapoint)
            self.size += 1

        if self.isFull():
            log.msg("MetricCache is full: self.size=%d" % self.size)

    def isFull(self):
        return self.max_size and self.size >= self.max_size

    def pop(self, metric):
        with self.lock:
            datapoints = dict.pop(self, metric)
            self.size -= len(datapoints)
            return datapoints

    def counts(self):
        with self.lock:
            return [(metric, len(datapoints)) for (metric, datapoints) in self.items()]

    def metrics(self):
        metrics = self.counts()
        metrics.sort(key=lambda item: item[1], reverse=True)

        for metric, queueSize in metrics:
            try:  # metrics can momentarily disappear from the MetricCache due to the implementation of MetricCache.store()
                datapoints = self.pop(metric)
            except KeyError:
                log.msg("MetricCache contention, skipping %s update for now" % metric)
                continue  # we simply move on to the next metric when this race condition occurs

            yield (metric, datapoints)


# Ghetto singleton
MetricCache = MetricCache()
