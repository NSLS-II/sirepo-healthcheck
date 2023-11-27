import datetime
import glob
import json
import os
import re
import shutil
import smtplib
import socket
import time
import asyncio
from argparse import Namespace
from email.message import EmailMessage
from pathlib import Path

import requests
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient

import playwright_workflow


def health_check(server=None, timeout=10.0):
    """Sirepo health check function.

    Parameters
    ----------
    server : str
        a server to check.
    timeout : float (optional)
        timeout for the request.

    Returns
    -------
    boolean value showing if the server is up.
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

    if r.status_code not in [200, 302]:
        print(
            f"The return code is {r.status_code}. "
            f"Something is wrong with {server}."
        )
        return False

    return True if re.search("APP_VERSION", r.text) else False


def send_status_email(subject, addressees, body, test=True):
    """Send a status email.

    Parameters
    ----------
    subject : str
        a subject string for the email.
    addressees : list
        a list of email addresses to send to.
    body : str
        a text body for the email.
    test : bool
        a flag for test mode (True by default).
    """
    subject = f"Sirepo: {subject}"
    content = body
    server_name = socket.gethostname()
    sender = f"Sirepo Health Check <sirepo@{server_name}>"
    msg = EmailMessage()
    msg.set_content(content)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = addressees

    if test:
        print(msg)
    else:
        s = smtplib.SMTP("localhost")
        s.send_message(msg)
        s.quit()


def post_slack_message(subject, content, test=False):
    """Post a status message to Slack.

    Parameters
    ----------
    subject : str
        a subject string to post.
    body : str
        a text body to post.
    test : bool
        a flag for test mode (False by default).
    """

    url = os.getenv("SLACK_WEBHOOK_URL", None)
    if url is None:
        raise RuntimeError('Define "SLACK_WEBHOOK_URL" env var!')
    webhook = WebhookClient(url)

    server_name = socket.gethostname()
    subject = f"Sirepo monitoring @ {server_name}: {subject}"

    if test:
        print(content)
    else:
        text = f"*{subject}*\n\n{content}"
        response = webhook.send(
            text=text,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                }
            ],
        )
        return response


def get_screenshots(url_list, output_dir):

    timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H.%M.%S')
    path = Path(output_dir) / timestamp
    path.mkdir(parents=True)
    coro = playwright_workflow.generate_screenshots(path)
    asyncio.run(coro)
    return path


def upload_files_to_slack(files):
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_token)
    for f in files:
        basename = os.path.basename(f)
        resp = client.files_upload(
            channels=os.environ["SLACK_POSTING_CHANNEL"],
            file=f,
            title=f"*{basename}* from '{socket.gethostname()}'",
        )
        print(f"Status code for uploading of {basename} is {resp.status_code}")


def update_status_file(status_file, statuses):
    with open(status_file, "w") as f:
        f.write(_to_json(statuses))


def _cleanup_output_dir(dirname):
    shutil.rmtree(dirname)


def _from_json(s):
    return json.loads(s)


def _from_json_file(file):
    with open(file) as f:
        return _from_json(f.read())


def _to_json(statuses):
    return json.dumps(
        statuses, sort_keys=True, indent=4, separators=(",", ": ")
    )


def main(test=True):
    servers = [
        # "https://raydata.nsls2.bnl.gov/raydata/",
        "http://127.0.0.1:8081/raydata",
        # "https://expdev-test.nsls2.bnl.gov/srw#/simulations",
        # "https://expdev.nsls2.bnl.gov/srw#/simulations",
        # 'https://expdev.nsls2.bnl.gov/light',
        # 'http://nsls2expdev1.bnl.gov:8000/light',
        # 'http://localhost:8000/light',
        # 'http://127.0.0.1:8000/light',
        # 'https://alpha.sirepo.com/light',
        # 'https://beta.sirepo.com/light',
    ]
    # addressees = []
    status_file = "sirepo_healthcheck.json"

    reminder_period = 120  # min

    statuses = {}
    datetime_format = "%Y-%m-%d %H:%M:%S"

    for server in servers:
        status = health_check(server=server)
        timestamp = time.time()
        statuses[server] = {
            "up": status,
            "check_timestamp": timestamp,
            "check_datetime": datetime.datetime.fromtimestamp(
                timestamp
            ).strftime(datetime_format),
            "last_seen_timestamp": timestamp if status else None,
            "last_seen_datetime": datetime.datetime.fromtimestamp(
                timestamp
            ).strftime(datetime_format)
            if status
            else None,
            "last_notified": None,
        }

    subject = ""
    msgs = []

    bool2str = {True: "up", False: "down"}

    if not os.path.isfile(status_file):
        # First run:
        subject = "monitoring started"
        msg = ""
        for k in statuses.keys():
            statuses[k]["last_notified"] = time.time()
            msg += f'- {k} ({bool2str[statuses[k]["up"]]})\n'
        msgs.append(f"{subject.capitalize()} for:\n{msg}")
    else:
        # File exists, check the status:
        previous_statuses = _from_json_file(status_file)

        changed = set(previous_statuses.keys()) ^ set(statuses.keys())
        # unchanged = set(previous_statuses.keys()) & set(statuses.keys())

        if changed:
            subject = "monitored servers changed"
            for k in changed:
                if k not in statuses.keys():
                    msgs.append(
                        f"Server {k} removed from monitoring "
                        f"({bool2str[previous_statuses[k]['up']]}) - last "
                        f"update {previous_statuses[k]['check_datetime']}"
                    )
                else:
                    msgs.append(
                        f"Server {k} added for monitoring "
                        f"({bool2str[statuses[k]['up']]}) - last update "
                        f"{statuses[k]['check_datetime']}"
                    )
            for k in statuses.keys():
                if not statuses[k]["up"]:
                    if k in previous_statuses.keys():
                        # Don't update last seen time for the down machines:
                        statuses[k]["last_seen_timestamp"] = previous_statuses[
                            k
                        ]["last_seen_timestamp"]
                        statuses[k]["last_seen_datetime"] = previous_statuses[
                            k
                        ]["last_seen_datetime"]
                        statuses[k]["last_notified"] = previous_statuses[k][
                            "last_notified"
                        ]
                    else:
                        statuses[k]["last_notified"] = time.time()
        else:
            subject = "status changed"
            for k in statuses.keys():
                if not statuses[k]["up"]:
                    if k in previous_statuses.keys():
                        # Don't update last seen time for the down machines:
                        statuses[k]["last_seen_timestamp"] = previous_statuses[
                            k
                        ]["last_seen_timestamp"]
                        statuses[k]["last_seen_datetime"] = previous_statuses[
                            k
                        ]["last_seen_datetime"]
                        statuses[k]["last_notified"] = previous_statuses[k][
                            "last_notified"
                        ]
                    else:
                        statuses[k]["last_notified"] = time.time()
                else:
                    if k in previous_statuses.keys():
                        statuses[k]["last_notified"] = previous_statuses[k][
                            "last_notified"
                        ]
                    else:
                        statuses[k]["last_notified"] = time.time()
                if previous_statuses[k]["up"] != statuses[k]["up"]:
                    statuses[k]["last_notified"] = time.time()
                    msgs.append(
                        f"{k}: {subject}: "
                        f"{bool2str[previous_statuses[k]['up']]} -> "
                        f"{bool2str[statuses[k]['up']]} "
                        f"({statuses[k]['check_datetime']})"
                    )
                else:
                    if not statuses[k]["up"]:
                        if (
                            not statuses[k]["last_notified"]
                            and not previous_statuses[k]["last_notified"]
                        ):
                            statuses[k]["last_notified"] = time.time()
                        else:
                            statuses[k]["last_notified"] = previous_statuses[
                                k
                            ]["last_notified"]
                        if (
                            statuses[k]["check_timestamp"]
                            - statuses[k]["last_notified"]
                        ) / 60 > reminder_period:  # remind after set minutes
                            statuses[k]["last_notified"] = statuses[k][
                                "check_timestamp"
                            ]
                            subject = "reminder about down server"
                            date_time = datetime.datetime.fromtimestamp(
                                time.time()
                            ).strftime(datetime_format)
                            msgs.append(
                                f"{k}: the server is down for more than "
                                f"{reminder_period} minutes "
                                f"({date_time})"
                            )

    update_status_file(status_file, statuses)
    if msgs:
        # send_status_email(subject, addressees, '\n'.join(msgs), test=test)
        post_slack_message(subject, "\n".join(msgs), test=test)

        output_dir = "/tmp/hw-sirepo-healthcheck-screenshots"

        output_subdir = get_screenshots(url_list=servers, output_dir=output_dir)

        files = glob.glob(os.path.join(output_subdir, "*.png"))
        upload_files_to_slack(files)


if __name__ == "__main__":
    main(test=False)
