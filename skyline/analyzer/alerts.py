from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from smtplib import SMTP

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("skyline.analyzer.alerts")


"""
Create any alerter you want here. The function will be invoked from trigger_alert.
Two arguments will be passed, both of them tuples: alert and metric.

metric: the anomalous metric
datapoint: the anomalous datapoint (timestamp, value)
ensemble: the ensemble result dictionary
args: alert specific settings (e.g. notification recipient)
settings: general alert settings (e.g. authentication information)
"""


# This specifies the mailserver to connect to.
# If user or password are blank no authentication is used.
def alert_smtp(metric, datapoint, ensemble, args, settings):
    # Connect to the mail server
    conn = SMTP(settings["host"])
    user = settings.get("user")
    password = settings.get("password")
    if user and password:
        conn.login(user, password)

    sender = settings['sender']
    recipients = args['recipients']
    for recipient in recipients:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '[Skyline] {0}'.format(metric)
        msg['From'] = sender
        msg['To'] = recipient
        link = ""  # settings.GRAPH_URL.format(metric)
        # body = 'Anomalous metric: {0} (datapoint: {1})<br><a href="{2}"><img src="{2}"/></a>'.format(metric, datapoint, link)
        body = 'Anomalous metric: {0} (datapoint: {1})'.format(metric, datapoint)
        msg.attach(MIMEText(body, 'html'))
        conn.sendmail(sender, recipients, msg.as_string())
    conn.quit()


def alert_pagerduty(metric, datapoint, ensemble, args, settings):
    import pygerduty
    pager = pygerduty.PagerDuty(settings['subdomain'], settings['auth_token'])
    pager.trigger_incident(settings['key'], "Anomalous metric: {0} (datapoint: {1})".format(metric, datapoint))


def alert_hipchat(metric, datapoint, ensemble, args, settings):
    import hipchat
    hipster = hipchat.HipChat(token=settings['auth_token'])
    rooms = args['rooms']
    link = ""  # settings.GRAPH_URL.format(metric)
    # body = 'Anomalous metric: {0} (datapoint: {1})<br><a href="{2}"><img src="{2}"/></a>'.format(metric, datapoint, link)
    body = 'Anomalous metric: {0} (datapoint: {1})'.format(metric, datapoint)
    for room in rooms:
        hipster.method('rooms/message', method='POST', parameters={'room_id': room,
                                                                   'from': 'Skyline',
                                                                   'color': settings.get('color', 'red'),
                                                                   'message': body})


def alert_stdout(metric, datapoint, ensemble, args, settings):
    logger.warning("metric={0} datapoint={1}".format(metric, datapoint))


def alert_syslog(metric, datapoint, ensemble, args, settings):
    import syslog
    syslog.openlog("skyline", syslog.LOG_PID, syslog.LOG_LOCAL4)
    syslog.syslog(syslog.LOG_LOCAL4, str("metric={0} datapoint={1}".format(metric, datapoint)))
