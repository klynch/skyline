## Skyline

[![Build Status](https://travis-ci.org/etsy/skyline.svg)](https://travis-ci.org/etsy/skyline)

![x](https://raw.github.com/etsy/skyline/master/screenshot.png)

Skyline is a real-time* anomaly detection* system*, built to enable passive
monitoring of hundreds of thousands of metrics, without the need to configure a
model/thresholds for each one, as you might do with Nagios. It is designed to be
used wherever there are a large quantity of high-resolution timeseries which
need constant monitoring. Once a metrics stream is set up (from StatsD or
Graphite or other source), additional metrics are automatically added to Skyline
for analysis. Skyline's easily extendible algorithms automatically detect what
it means for each metric to be anomalous. After Skyline detects an anomalous
metric, it surfaces the entire timeseries to the webapp, where the anomaly can be
viewed and acted upon.

Read the details in the [wiki](https://github.com/etsy/skyline/wiki).

## Install

1. `sudo pip install -r requirements.txt` for the easy bits

2. Install numpy, scipy, pandas, patsy, statsmodels, msgpack_python in that
order.

2. You may have trouble with SciPy. If you're on a Mac, try:

* `sudo port install gcc48`
* `sudo ln -s /opt/local/bin/gfortran-mp-4.8 /opt/local/bin/gfortran`
* `sudo pip install scipy`

On Debian, apt-get works well for Numpy and SciPy. On Centos, yum should do the
trick. If not, hit the Googles, yo.

3. `cp src/settings.py.example src/settings.py`

4. Add directories:

```
sudo mkdir /var/log/skyline
sudo mkdir /var/run/skyline
sudo mkdir /var/log/redis
sudo mkdir /var/dump/
```

5. Download and install the latest Redis release

6. Start 'er up

* `cd skyline/bin`
* `sudo redis-server redis.conf`
* `sudo ./horizon.d start`
* `sudo ./analyzer.d start`
* `sudo ./webapp.d start`

By default, the webapp is served on port 1500.

7. Check the log files to ensure things are running.

[Debian + Vagrant specific, if you prefer](https://github.com/etsy/skyline/wiki/Debian-and-Vagrant-Installation-Tips)

### Gotchas

* If you already have a Redis instance running, it's recommended to kill it and
restart using the configuration settings provided in bin/redis.conf

* Be sure to create the log directories.

### Hey! Nothing's happening!
Of course not. You've got no data! For a quick and easy test of what you've
got, run this:
```
cd utils
python seed_data.py
```
This will ensure that the Horizon
service is properly set up and can receive data. For real data, you have some
options - see [wiki](https://github.com/etsy/skyline/wiki/Getting-Data-Into-Skyline)

Once you get real data flowing through your system, the Analyzer will be able
start analyzing for anomalies!  But be aware, analyzer it will only start to really analyzing timeseries when redis has `FULL_DURATION` (e.g. 86400 seconds) worth of data, otherwise it is too short aka less than `MIN_TOLERABLE_LENGTH`.

### Alerts

Skyline can alert you! In your settings.py, add any alerts you want to the ALERTS list, according to the schema `(metric
pattern, strategy, expiration timeout seconds, strategy arguments)` where `strategy` is one of `smtp`, `hipchat`,
`pagerduty`, `syslog`, or `stdout`.  Wildcards can be used in the `metric keyword` as well. You can also add your own
alerting strategies.  For every anomalous metric, Skyline will search for the given keyword and trigger the
corresponding alert(s). To prevent alert fatigue, Skyline will only alert once every <expiration seconds> for any given
metric/strategy combination. To enable Hipchat integration, uncomment the python-simple-hipchat line in the
requirements.txt file.  If using syslog then the `EXPIRATION_TIME` should be set to 1 for this to be effective in
catching every anomaly, e.g.  `("stats", "syslog", 1)`

This is the config for which metrics to alert on and which strategy to use for each.  Alerts will not fire twice within
`timeout` period, even if they trigger again.  This is stored as JSON data in the Redis key `skyline:alerts:rules` with the
following schema:

    Schema: [
               [pattern, strategy, timeout, arguments],
            ]

where pattern is a regular expression string, alert is an identifier for the alert, expiration timeout is the time the
alert/metric pair is quiet for, and arguments is an alert specific dictionary.

    ALERTS = [
        [".*",      "stdout",    1800, {}],
        ["skyline", "smtp",      1800, { "recipients": ["sre@squarespace.com"] }],
        ["metric1", "hipchat",   1800, { "rooms": [12345] }],
        ["metric2", "pagerduty", 1800, { "rooms": [12345] }],
    ]


General alert settings are stored as a JSON blob in the Redis key `skyline:alerts:settings`.

    ALERT_SETTINGS = {
        #This specifies the mailserver to connect to. If user or password are blank no authentication is used.
        "smtp": {
            "host": "127.0.0.1:25",
            "user": "skyline",
            "password": "",
            "sender": "skyline-alerts@etsy.com",
        },

        # HipChat alerts require python-simple-hipchat
        # Background color is one of "yellow", "red", "green", "purple", "gray", or "random"
        "hipchar": {
            "auth_token": "pagerduty_auth_token",
            "color": "purple",
        },

        # PagerDuty alerts require pygerduty
        # Requires pagerduty subdomain and auth token and Service API key (shown on the detail page of a "Generic API" service)
        "pagerduty": {
            "subdomain": "example",
            "auth_token": "your_pagerduty_auth_token",
            "key": "your_pagerduty_service_api_key",
        },
    }


### How do you actually detect anomalies?
An ensemble of algorithms vote. Majority rules. Batteries __kind of__ included.
See [wiki](https://github.com/etsy/skyline/wiki/Analyzer)

### Architecture
See the rest of the
[wiki](https://github.com/etsy/skyline/wiki)

### Contributions
1. Clone your fork
2. Hack away
3. If you are adding new functionality, document it in the README or wiki
4. If necessary, rebase your commits into logical chunks, without errors
5. Verfiy your code by running the test suite and pep8, adding additional tests if able.
6. Push the branch up to GitHub
7. Send a pull request to the etsy/skyline project.

We actively welcome contributions. If you don't know where to start, try
checking out the [issue list](https://github.com/etsy/skyline/issues) and
fixing up the place. Or, you can add an algorithm - a goal of this project
is to have a very robust set of algorithms to choose from.

Also, feel free to join the
[skyline-dev](https://groups.google.com/forum/#!forum/skyline-dev) mailing list
for support and discussions of new features.

(*depending on your data throughput, *you might need to write your own
algorithms to handle your exact data, *it runs on one box)
