import datetime
import json
import os
import re
import smtplib
import socket
import time
from email.message import EmailMessage

import requests


def health_check(server=None, timeout=10.0):
    """Sirepo health check function.

    :param server: a server to check.
    :param timeout: timeout for the request.
    :return: boolean value showing if the server is up.
    """
    try:
        r = requests.get(
            url=server,
            params=None,
            timeout=timeout,
        )
    except requests.exceptions.ReadTimeout:
        return False
    except requests.exceptions.ConnectionError:
        return False

    if r.status_code != 200:
        print(f'The return code is {r.status_code}. '
              f'Something is wrong with {server}.')
        return False

    return True if re.search('APP_VERSION', r.text) else False


def send_status_email(subject, addressees, body, test=True):
    subject = f'Sirepo: {subject}'
    content = body
    server_name = socket.gethostname()
    sender = f'Sirepo Health Check <sirepo@{server_name}>'
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = addressees

    if test:
        print(msg)
    else:
        s = smtplib.SMTP('localhost')
        s.send_message(msg)
        s.quit()


def update_status_file(status_file, statuses):
    with open(status_file, 'w') as f:
        f.write(_to_json(statuses))


def _from_json(s):
    return json.loads(s)


def _from_json_file(file):
    with open(file) as f:
        return _from_json(f.read())


def _to_json(statuses):
    return json.dumps(statuses, sort_keys=True, indent=4, separators=(',', ': '))


def main(test=True):
    servers = [
        'https://expdev-test.nsls2.bnl.gov/srw#/simulations',
        'https://expdev.nsls2.bnl.gov/srw#/simulations',
        #'https://expdev.nsls2.bnl.gov/light',
        #'http://nsls2expdev1.bnl.gov:8000/light',
        # 'http://localhost:8000/light',
        # 'http://127.0.0.1:8000/light',
        # 'https://alpha.sirepo.com/light',
        # 'https://beta.sirepo.com/light',
    ]
    addressees = [
        'anhe@bnl.gov',
        'ahe@bnl.gov',
        'heananhe@gmail.com',
        #'mrakitin@bnl.gov',
        #'maxim.rakitin@gmail.com',
        #'chubar@bnl.gov',
        #'lwiegart@bnl.gov',
    ]
    # status_file = '/tmp/sirepo_healthcheck.json'
    status_file = 'sirepo_healthcheck.json'

    reminder_period = 120  # min

    statuses = {}
    datetime_format = '%Y-%m-%d %H:%M:%S'

    for server in servers:
        status = health_check(server=server)
        timestamp = time.time()
        statuses[server] = {
            'up': status,
            'check_timestamp': timestamp,
            'check_datetime': datetime.datetime.fromtimestamp(timestamp).strftime(datetime_format),
            'last_seen_timestamp': timestamp if status else None,
            'last_seen_datetime': datetime.datetime.fromtimestamp(timestamp).strftime(
                datetime_format) if status else None,
            'last_notified': None,
        }

    subject = ''
    msgs = []

    bool2str = {
        True: 'up',
        False: 'down'
    }

    if not os.path.isfile(status_file):
        # First run:
        subject = 'monitoring started'
        msg = ''
        for k in statuses.keys():
            statuses[k]['last_notified'] = time.time()
            msg += f'- {k} ({bool2str[statuses[k]["up"]]})\n'
        msgs.append(f'{subject.capitalize()} for:\n{msg}')
    else:
        # File exists, check the status:
        previous_statuses = _from_json_file(status_file)

        changed = set(previous_statuses.keys()) ^ set(statuses.keys())
        # unchanged = set(previous_statuses.keys()) & set(statuses.keys())

        if changed:
            subject = 'monitored servers changed'
            for k in changed:
                if k not in statuses.keys():
                    msgs.append(
                        f"Server {k} removed from monitoring ({bool2str[previous_statuses[k]['up']]}) - last update {previous_statuses[k]['check_datetime']}")
                else:
                    msgs.append(
                        f"Server {k} added for monitoring ({bool2str[statuses[k]['up']]}) - last update {statuses[k]['check_datetime']}")
            for k in statuses.keys():
                if not statuses[k]['up']:
                    if k in previous_statuses.keys():
                        # Don't update last seen time for the down machines:
                        statuses[k]['last_seen_timestamp'] = previous_statuses[k]['last_seen_timestamp']
                        statuses[k]['last_seen_datetime'] = previous_statuses[k]['last_seen_datetime']
                        statuses[k]['last_notified'] = previous_statuses[k]['last_notified']
                    else:
                        statuses[k]['last_notified'] = time.time()
        else:
            subject = 'status changed'
            for k in statuses.keys():
                if not statuses[k]['up']:
                    if k in previous_statuses.keys():
                        # Don't update last seen time for the down machines:
                        statuses[k]['last_seen_timestamp'] = previous_statuses[k]['last_seen_timestamp']
                        statuses[k]['last_seen_datetime'] = previous_statuses[k]['last_seen_datetime']
                        statuses[k]['last_notified'] = previous_statuses[k]['last_notified']
                    else:
                        statuses[k]['last_notified'] = time.time()
                else:
                    if k in previous_statuses.keys():
                        statuses[k]['last_notified'] = previous_statuses[k]['last_notified']
                    else:
                        statuses[k]['last_notified'] = time.time()
                if previous_statuses[k]['up'] != statuses[k]['up']:
                    statuses[k]['last_notified'] = time.time()
                    msgs.append(
                        f"{k}: {subject}: {bool2str[previous_statuses[k]['up']]} -> {bool2str[statuses[k]['up']]} ({statuses[k]['check_datetime']})")
                else:
                    if not statuses[k]['up']:
                        if not statuses[k]['last_notified'] and not previous_statuses[k]['last_notified']:
                            statuses[k]['last_notified'] = time.time()
                        else:
                            statuses[k]['last_notified'] = previous_statuses[k]['last_notified']
                        if (statuses[k]['check_timestamp'] - statuses[k][
                            'last_notified']) / 60 > reminder_period:  # remind after set minutes
                            statuses[k]['last_notified'] = statuses[k]['check_timestamp']
                            subject = 'reminder about down server'
                            msgs.append(
                                f"{k}: the server is down for more than {reminder_period} minutes ({datetime.datetime.fromtimestamp(time.time()).strftime(datetime_format)})")

    update_status_file(status_file, statuses)
    if msgs:
        send_status_email(subject, addressees, '\n'.join(msgs), test=test)


if __name__ == '__main__':
    main(test=False)
