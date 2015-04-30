import json
import redis
import socket
import time


def verify_metric_exists(api, metric):
    if metric not in api.get_metricset_all():
        raise Exception("Missing metric in set: {0}".format(metric))
    if not api.get_metric_data(metric):
        raise Exception("Missing metric data: {0}".format(metric))
    if not api.get_metric_info(metric):
        raise Exception("Missing metric info: {0}".format(metric))


def seed_line(host, port, metric, timeseries, initial):
    sock = socket.socket()
    sock.connect((host, port))
    for datapoint in timeseries:
        datapoint[0] = initial
        initial += 1
        sock.sendall("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]).encode('utf-8'))
    sock.close()
    return metric


def seed_udp(host, port, metric, timeseries, initial):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for datapoint in timeseries:
        datapoint[0] = initial
        initial += 1
        sock.sendto("{0} {1} {2}\n".format(metric, datapoint[1], datapoint[0]).encode('utf-8'), (host, port))
    return metric


def seed_data(api, data_file, max_resolution, host, prefix='horizon', line_port=0, udp_port=0, verify=True):
    try:
        timeseries = []
        with open(data_file, 'r') as f:
            data = json.loads(f.read())
            timeseries = data['results']

        initial = int(time.time()) - max_resolution
        if line_port:
            print('Loading data over line via Horizon...')
            metric = '{0}.test.line'.format(prefix)
            seed_line(host, line_port, metric, timeseries, initial)
            if verify:
                verify_metric_exists(api, metric)
        if udp_port:
            print('Loading data over udp via Horizon...')
            metric = '{0}.test.udp'.format(prefix)
            seed_udp(host, udp_port, metric, timeseries, initial)
            if verify:
                verify_metric_exists(api, metric)
    except Exception as e:
        print(e)
