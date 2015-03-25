import argparse
import redis
import logging
import simplejson as json
import sys
from msgpack import Unpacker
from flask import Flask, request, render_template
from os.path import dirname, abspath

# add the shared settings file to namespace
sys.path.insert(0, dirname(dirname(abspath(__file__))))
import settings

REDIS_CONN = None

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.route("/")
def index():
    return render_template('index.html'), 200


@app.route("/app_settings")
def app_settings():
    app_settings = {'GRAPH_URL': settings.GRAPH_URL,
                    }
    resp = json.dumps(app_settings)
    return resp, 200


@app.route("/api/anomalies", methods=['GET'])
def anomalies():
    resp = "handle_data()"
    return resp, 200


@app.route("/api/metric", methods=['GET'])
def data():
    metric = request.args.get('metric', None)
    try:
        raw_series = REDIS_CONN.get(metric)
        if not raw_series:
            resp = json.dumps({'results': 'Error: No metric by that name'})
            return resp, 404
        else:
            unpacker = Unpacker(use_list = False)
            unpacker.feed(raw_series)
            timeseries = [item[:2] for item in unpacker]
            resp = json.dumps({'results': timeseries})
            return resp, 200
    except Exception as e:
        error = "Error: " + e
        resp = json.dumps({'results': error})
        return resp, 500


if __name__ == "__main__":
    """
    Start the server
    """
    parser = argparse.ArgumentParser(description='Webapp to display anomalies.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="The IP address for the webapp")
    parser.add_argument("-p", "--port", type=int, default=1500, help="The port for the webapp")
    args = parser.parse_args()

    REDIS_CONN = redis.StrictRedis.from_url(args.redis)

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("AppLog")
    logger.info('starting webapp')
    app.run(args.host, args.port)
