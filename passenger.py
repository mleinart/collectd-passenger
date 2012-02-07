# passenger-collectd-plugin - passenger.py
#
# Author: Michael Leinartas
# Description: This is a collectd plugin which runs under the Python plugin to
# collect metrics from passenger.

import collectd
import errno
import os
import socket
import struct
from glob import glob
from xml.dom import minidom

NAME = 'passenger'
DEFAULT_PASSENGER_TEMP_DIR = '/tmp'
IGNORED_METRICS = [ 'max' ]
HEADER_PAD = 2
HEADER_SIZE = 2
DELIMITER = '\0'

class PassengerSocket(object):
  def __init__(self, socket_file):
    self.socket_file = socket_file

  @staticmethod
  def find_sockets(temp_dir=DEFAULT_PASSENGER_TEMP_DIR):
    result = []
    passenger_dirs = glob(os.path.join(temp_dir, 'passenger.*'))
    for passenger_dir in passenger_dirs:
      pid = passenger_dir.split('.')[1]
      try:
        os.kill(int(pid), 0)
      except OSError, e:
        if e.errno != errno.EPERM:
          continue
      socket_path = os.path.join(passenger_dir, 'info', 'status.socket')

      if os.path.exists(socket_path):
        result.append(socket_path)
    return result

  def connect(self):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(self.socket_file)
    return sock

  def communicate(self, command):
    ''' Send a single command to the socket and return a list of response elements '''
    # This logic is copied from passenger's message_channel.rb
    # It seems necessary as passenger doesnt always return data if you just bulk read
    passenger_socket = self.connect()
    command += '\0'

    passenger_socket.send(struct.pack('!H', len(command)) + command)

    buf = ''
    while len(buf) < HEADER_PAD + HEADER_SIZE:
      buf += passenger_socket.recv(HEADER_PAD + HEADER_SIZE - len(buf))

    size = struct.unpack('!H', buf[HEADER_PAD:])[0]
    if size == 0:
      return ''

    buf = ''
    while len(buf) < size:
      buf += passenger_socket.recv(size - len(buf))

    passenger_socket.close()
    return buf

  def get_status_xml(self):
    return self.communicate('status_xml')

  def get_status_text(self):
    return self.communicate('status')

  def get_server_stats(self):
    # Python 2.4 support so we use minidom..
    dom = minidom.parseString(self.get_status_xml())
    server_info = {}
    for domain_el in dom.getElementsByTagName('domain'):
      domain = domain_el.firstChild.nodeValue
      server_info[domain] = []

      for instance_el in domain_el.getElementsByTagName('instance'):
        for data_el in instance_el.childNodes:
          server_info[domain][data_el.tagName] = data_el.firstChild.nodeValue

    return minidom

  def get_server_summary(self):
    result = {}
    status_text = self.get_status_text()
    if not status_text:
      return result
    for line in status_text.splitlines():
      if 'Domains' in line:
        break
      if '=' in line:
        key,val = line.split('=')
        result[key.strip()] = val.strip()
      elif 'queue:' in line:
        val = line.split(':')[1]
        result['queued'] = val

    return result

def get_stats():
  stats = dict()
  running_sockets = PassengerSocket.find_sockets(PASSENGER_TEMP_DIR)
  if len(running_sockets) == 0:
    logger('error', "Unable to find running or accessible Passenger instances in '%s'" % PASSENGER_TEMP_DIR)
    return stats
  elif len(running_sockets) > 1:
    logger('warn', "More than one Passenger socket discovered in '%s', using the first found" % PASSENGER_TEMP_DIR)

  logger('debug', "Opening socket at '%s'" % running_sockets[0])
  passenger = PassengerSocket(running_sockets[0])

  try:
    server_summary = passenger.get_server_summary()
    logger('debug', "Read from socket sucessfully")
  except socket.error, e:
    logger('warn', "Unable to connect to Passenger socket at '%s'" % passenger.socket_file)
    return stats

  if not server_summary:
    return stats

  for key,val in server_summary.items():
    if key in IGNORED_METRICS:
      continue

    try:
      stats[key] = int(val)
    except (TypeError, ValueError), e:
      logger('debug', "Received a value of unknown type for stat '%s' with value '%s': %s" % (key, val, e))

  return stats

def configure_callback(conf):
  global PASSENGER_TEMP_DIR, VERBOSE_LOGGING
  PASSENGER_TEMP_DIR = DEFAULT_PASSENGER_TEMP_DIR
  VERBOSE_LOGGING = False

  for node in conf.children:
    if node.key == "PassengerTempDir":
      PASSENGER_TEMP_DIR = node.values[0]
    elif node.key == "Verbose":
      VERBOSE_LOGGING = bool(node.values[0])
    else:
      logger('warn', 'Unknown config key: %s' % node.key)

def read_callback():
  logger('verb', "beginning read_callback")
  info = get_stats()

  if not info:
    logger('warn', "%s: No data received" % NAME)
    return

  for key,value in info.items():
    collectd_value = collectd.Values(plugin=NAME, type='gauge')
    collectd_value.type_instance = key
    collectd_value.values = [ value ]
    collectd_value.dispatch()

def logger(t, msg):
    if t == 'err':
        collectd.error('%s: %s' % (NAME, msg))
    elif t == 'warn':
        collectd.warning('%s: %s' % (NAME, msg))
    elif t == 'verb' and VERBOSE_LOGGING:
        collectd.info('%s: %s' % (NAME, msg))
    else:
        collectd.notice('%s: %s' % (NAME, msg))

collectd.register_config(configure_callback)
collectd.register_read(read_callback)
