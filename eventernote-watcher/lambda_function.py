#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import mechanicalsoup
import re
import os
import time
import json
import urllib

BASE_URL = "https://www.eventernote.com"
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

def lambda_handler(event, context):
    br = mechanicalsoup.StatefulBrowser()
    br.open(BASE_URL + "/login")
    br.select_form("#login_form")
    br["email"] = os.environ["EVENTERNOTE_USERNAME"]
    br["password"] = os.environ["EVENTERNOTE_PASSWORD"]
    br.submit_selected()

    br.open(BASE_URL + "/users/notice")

    event_dict = {}
    for event in [
        e for e in br.get_current_page().select("div.gb_timeline_list > ul > li")
        if not re.search("(日前|年前)", e.find("span").text)
        and e.attrs["class"] != "past" ]:

        cast = event.find("a").text
        title = event.find_all("a")[1].text
        url = BASE_URL + event.find_all("a")[1].attrs["href"]

        if not title in event_dict:
            event_dict[title] = {"cast": [cast], "url": url}
        else:
            event_dict[title]["cast"].append(cast)

    text = ""
    for k, v in event_dict.items():
        text += "[%s] %s %s\n" % (", ".join(sorted(v["cast"])), k, v["url"])

    payload = {
            "text": text,
            "channel": "#event",
            }
    binary_data = json.dumps(payload).encode("utf8")
    urllib.request.urlopen(SLACK_WEBHOOK_URL, binary_data)

if __name__ == "__main__":
    lambda_handler(None, None)
