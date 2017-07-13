#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import boto3
import mechanicalsoup
import re
import os
import time
import json
import urllib
import logging
from base64 import b64decode

kms = boto3.client("kms")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

BASE_URL = "https://www.eventernote.com"

def lambda_handler(event, context):
    envs = ["EVENTERNOTE_USERNAME", "EVENTERNOTE_PASSWORD", "SLACK_WEBHOOK_URL"]
    username, password, webhook_url = [
        kms.decrypt(CiphertextBlob=b64decode(os.environ[env]))['Plaintext'].decode('utf8')
        for env in envs
    ]

    br = mechanicalsoup.StatefulBrowser()
    br.open(BASE_URL + "/login")
    br.select_form("#login_form")
    br["email"] = username
    br["password"] = password
    br.submit_selected()
    br.open(BASE_URL + "/users/notice")

    event_dict = {}
    new_events = br.get_current_page().select("div.gb_timeline_list > ul > li")
    for event in [
        e for e in reversed(new_events)
        if not re.search("(日前|年前)", e.find("span").text)
        and e.attrs["class"] != "past"
    ]:
        cast = event.find("a").text
        title = event.find_all("a")[1].text
        url = BASE_URL + event.find_all("a")[1].attrs["href"]

        if not title in event_dict:
            event_dict[title] = {"cast": [cast], "url": url}
        else:
            event_dict[title]["cast"].append(cast)

    if len(event_dict.keys()) == 0:
        logger.info("no events")
        return

    text = "New %d events:\n\n" % len(event_dict)
    for k, v in event_dict.items():
        text += "[%s] %s %s\n" % (", ".join(sorted(list(set(v["cast"])))), k, v["url"])

    payload = {
        "text": text,
    }
    logger.info(payload)

    binary_data = json.dumps(payload).encode("utf8")
    urllib.request.urlopen(webhook_url, binary_data)

if __name__ == "__main__":
    lambda_handler(None, None)
