import json
import socket
import time
from .analyzer import Analyzer


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import cPickle as pickle
    USING_CPICKLE = True
except:
    import pickle
    USING_CPICKLE = False

# This whole song & dance is due to pickle being insecure
# yet performance critical for carbon. We leave the insecure
# mode (which is faster) as an option (USE_INSECURE_UNPICKLER).
# The SafeUnpickler classes were largely derived from
# http://nadiana.com/python-pickle-insecure
if USING_CPICKLE:
    class SafeUnpickler(object):
        PICKLE_SAFE = {
            'copy_reg': set(['_reconstructor']),
            '__builtin__': set(['object']),
        }

        @classmethod
        def find_class(cls, module, name):
            if module not in cls.PICKLE_SAFE:
                raise pickle.UnpicklingError('Attempting to unpickle unsafe module %s' % module)
            __import__(module)
            mod = sys.modules[module]
            if name not in cls.PICKLE_SAFE[module]:
                raise pickle.UnpicklingError('Attempting to unpickle unsafe class %s' % name)
            return getattr(mod, name)

        @classmethod
        def loads(cls, pickle_string):
            pickle_obj = pickle.Unpickler(StringIO(pickle_string))
            pickle_obj.find_global = cls.find_class
            return pickle_obj.load()

else:
    class SafeUnpickler(pickle.Unpickler):
        PICKLE_SAFE = {
            'copy_reg': set(['_reconstructor']),
            '__builtin__': set(['object']),
        }

        def find_class(self, module, name):
            if module not in self.PICKLE_SAFE:
                raise pickle.UnpicklingError('Attempting to unpickle unsafe module %s' % module)
            __import__(module)
            mod = sys.modules[module]
            if name not in self.PICKLE_SAFE[module]:
                raise pickle.UnpicklingError('Attempting to unpickle unsafe class %s' % name)
            return getattr(mod, name)

        @classmethod
        def loads(cls, pickle_string):
            return cls(StringIO(pickle_string)).load()
# //SafeUnpickler


def send_graphite_metric(graphite_host, graphite_port, name, value):
    if graphite:
        try:
            sock = socket.socket()
            sock.connect((graphite_host, graphite_port))
            sock.sendall('%s %s %i\n' % (name, value, time.time()))
            sock.close()
            return True
        except socket.error:
            logger.error("Can't connect to Graphite at {}:{}".format(graphite_host, graphite_port))
    return False


def check_alert(api, args, metric, trigger):
    print("Verifying alerts for: {}".format(metric))

    print("rules: {}".format(api.get_alerts_rules()))
    print("settings: {}".format(api.get_alerts_settings()))

    a = Analyzer(api, args)
    for t in a.alert(metric, (time.time(), 0), {}, check=True, trigger=trigger):
        print(t)


def check_anomalies(api, timestamp=True):
    for anomaly in api.get_anomalies(timestamp):
        if timestamp:
            print("{0}\t{1}".format(time.ctime(anomaly[1]), anomaly[0]))
        else:
            print("{0}".format(anomaly[0]))


def settings(api, import_file=None, export=True):
    if import_file:
        with open(import_file) as f:
            api.import_settings(json.load(f))
    if export:
        print(json.dumps(api.export_settings(), indent=4, sort_keys=True))


def print_metric_data(api, metric, interval):
    data = api.get_metric_data(metric)
    if not data:
        print("data not found for {0}".format(args.metric))
        return

    length = len(data)
    start = time.ctime(int(data[0][0]))
    end = time.ctime(int(data[-1][0]))
    duration = (float(data[-1][0]) - float(data[0][0]))

    last = int(data[0][0]) - 10
    bad = 0
    missing = 0
    for d in data:
        delta = int(d[0]) - last
        if delta > interval:
            bad += 1
            missing += delta
        last = d[0]

    print("Metric Data")
    print("  Stats for {} (interval={}):".format(metric, interval))
    print("  Start time:         {}".format(start))
    print("  End time:           {}".format(end))
    print("  Duration:           {} hours".format(duration / 3600))
    print("  Missing datapoints: {}".format(bad))
    print("  Missing time:       {} seconds".format(missing))
    print("  Datapoints:         {}".format(length))
    print("  Min Datapoint:      {}".format(min(d[1] for d in data)))
    print("  Max Datapoint:      {}".format(max(d[1] for d in data)))
    print("  Ave Datapoint:      {}".format(sum(d[1] for d in data) / length))


def print_metric_info(api, metric):
    info = api.get_metric_info(metric)
    if info:
        print("Metric Info")
        for k, v in info.items():
            print("  {0}: {1}".format(k, v))


def print_metric_last_analyzed_results(api, metric):
    results = api.get_last_analyzed_results(metric)
    if results:
        print("Last Analyzed Results")
        for k, v in results.items():
            print("  {0}: {1}".format(k, v))


def print_metric_last_anomaly_results(api, metric):
    results = api.get_last_analyzed_results(metric)
    if results:
        print("Last Anomaly Results")
        for k, v in results.items():
            print("  {0}: {1}".format(k, v))


def check_metric(api, metric, interval):
    print_metric_data(api, metric, interval)
    print("")
    print_metric_info(api, metric)
    print("")
    print_metric_last_analyzed_results(api, metric)
    print("")
    print_metric_last_anomaly_results(api, metric)
