import os
import time, datetime
import re
import smtplib
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

    up = None
    if re.search('APP_VERSION', r.text):
        up = True
    return up


def send_status_email(server, status, addressees, test=True):
    if test:
        return
    subject = f'Sirepo status at {server}'
    content = f'{server}: {status}'
    sender = 'Sirepo Health Check <sirepo@cpu-001>'

    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = addressees

    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

def create_status_file(status_file):
    ...

if __name__ == '__main__':
    servers = [
        'https://expdev.nsls2.bnl.gov/light',
        # 'https://google.com',
        'http://nsls2expdev1.bnl.gov:8000/light',
    ]
    addressees = [
        'mrakitin@bnl.gov',
        'maxim.rakitin@gmail.com',
    ]
    test = True
    status_file = '/tmp/sirepo_healthcheck.json'

    statuses = {}

    for server in servers:
        status = health_check(server=server)
        print(f'{server}: {status}')
        timestamp = time.time()
        statuses[server] = {
                               'status': status,
                               'timestamp': timestamp,
                               'datetime': datetime.datetime.fromtimestamp(timestamp),
                           }
    if not status:
        if not os.path.isfile(status_file):
            create_status_file(status_file)
            send_status_email(server=server, status=status, addressees=addressees, test=test)

