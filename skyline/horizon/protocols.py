from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import DatagramProtocol, ServerFactory
from twisted.protocols.basic import LineOnlyReceiver, Int32StringReceiver
from twisted.python import log
from skyline.utils import SafeUnpickler

from cache import MetricCache
from regexlist import WhiteList, BlackList

def emit(metric, value):
    log.msg(metric + " " + value)

class MetricReceiver:
  """ Base class for all metric receiving protocols, handles flow
  control events and connection state logging.
  """
  def connectionMade(self):
    self.peerName = self.transport.getPeer()
    log.msg("%s connection with %s established" % (self.__class__.__name__, self.peerName))

  def connectionLost(self, reason):
    if reason.check(ConnectionDone):
      log.msg("%s connection with %s closed cleanly" % (self.__class__.__name__, self.peerName))
    else:
      log.msg("%s connection with %s lost: %s" % (self.__class__.__name__, self.peerName, reason.value))

  def metricReceived(self, metric, datapoint):
    if BlackList and metric in BlackList:
      emit('skyline.horizon.blacklistMatches', metric)
      return
    if WhiteList and metric not in WhiteList:
      emit('skyline.horizon.whiteListRejects', metric)
      return
    MetricCache.store(metric, datapoint)


class MetricLineReceiver(MetricReceiver, LineOnlyReceiver):
  delimiter = '\n'

  def lineReceived(self, line):
    try:
      metric, value, timestamp = line.strip().split()
      self.metricReceived(metric, (float(timestamp), float(value)))
    except:
      log.msg('invalid line (%s) received from client %s, ignoring' % (line.strip(), self.peerName))


class MetricPickleReceiver(MetricReceiver, Int32StringReceiver):
  MAX_LENGTH = 2 ** 20

  def connectionMade(self):
    MetricReceiver.connectionMade(self)
    ##Use the safe unpickler that comes with carbon rather than standard python pickle/cpickle
    self.unpickler = SafeUnpickler

  def stringReceived(self, data):
    try:
      datapoints = self.unpickler.loads(data)
    except:
      log.msg('invalid pickle received from %s, ignoring' % self.peerName)
      return

    for (metric, datapoint) in datapoints:
      try:
        datapoint = ( float(datapoint[0]), float(datapoint[1]) ) #force proper types
      except:
        continue

      self.metricReceived(metric, datapoint)


class MetricDatagramReceiver(MetricReceiver, DatagramProtocol):
  def datagramReceived(self, data, (host, port)):
    for line in data.splitlines():
      try:
        metric, value, timestamp = line.strip().split()
        self.metricReceived(metric, (float(timestamp), float(value)))
      except:
        log.msg('invalid line (%s) received from %s, ignoring' % (line, host))


class MetricLineFactory(ServerFactory):
    protocol = MetricLineReceiver


class MetricPickleFactory(ServerFactory):
    protocol = MetricPickleReceiver
