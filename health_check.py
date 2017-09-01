import re
import smtplib
from email.mime.text import MIMEText

import requests


def health_check(server=None, timeout=30.0):
    """Sirepo health check function.

    :param server: a server to check.
    :param timeout: timeout for the request.
    :return: boolean value showing if the server is up.
    """
    r = requests.get(
        url=server,
        params=None,
        timeout=timeout,
    )
    up = False
    if re.search('APP_VERSION', r.text):
        up = True
    return up


def send_status_email(server, status, addressees):
    msg = MIMEText(f'{server}: {status}')

    sender = 'Sirepo Health Check'
    # you == the recipient's email address
    msg['Subject'] = f'Sirepo status at {server}'
    msg['From'] = sender
    msg['To'] = addressees

    s = smtplib.SMTP('127.0.0.1')
    s.sendmail(sender, addressees, msg.as_string())
    s.quit()


if __name__ == '__main__':
    servers = [
        'https://expdev.nsls2.bnl.gov/light',
        'https://google.com',
        'http://nsls2expdev1:8000/light',
    ]
    addressees = [
        'mrakitin@bnl.gov',
        'maxim.rakitin@gmail.com',
    ]

    for server in servers:
        status = health_check(server=server)
        print(f'{server}: {status}')
        if not status:
            send_status_email(server=server, status=status, addressees=addressees)
