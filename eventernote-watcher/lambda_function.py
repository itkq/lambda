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
    new_events = sorted(
        br.get_current_page().select("div.gb_timeline_list > ul > li"),
        key=lambda e: e.find_all("a")[1].text
    )
    for event in [
        e for e in reversed(new_events)
        if not re.search("(日前|年前)", e.find("span").text)
            and e.attrs["class"] != "past"
            and not re.search("重複", e.find_all("a")[1].text)
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

    cast_dict = {}
    for k, v in event_dict.items():
        casts = " / ".join(sorted(set(v["cast"])))

        if not casts in cast_dict:
            cast_dict[casts] = []

        cast_dict[casts].append({"event": k, "url": v["url"]})

    text = "New %d events:\n\n" % len(event_dict)

    for k, v in cast_dict.items():
        text += "【%s】\n" % k

        for vv in sorted(v, key=lambda e: e["event"]):
            text += "・<%s|%s>\n" % (vv["url"], vv["event"])

    payload = {
        "text": text,
    }
    logger.info(payload)

    binary_data = json.dumps(payload).encode("utf8")
    urllib.request.urlopen(webhook_url, binary_data)

if __name__ == "__main__":
    lambda_handler(None, None)
