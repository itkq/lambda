#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import boto3
import os
import re
from bs4 import BeautifulSoup
from urllib import request
from http import cookiejar
from twitter import *
import logging
from base64 import b64decode
import time
from datetime import datetime

BASE_NOW_URL = "http://now.ameba.jp"
SEARCH_LIMIT_INDEX = 1
DYNAMODB_TABLE_NAME = "AmebaCrawling"
TWEET_SIZE = 140
MAX_IMAGES_PER_TWEET = 4

kms = boto3.client("kms")
dynamodb = boto3.client("dynamodb")

envs = ["ACCESS_TOKEN", "ACCESS_SECRET", "CONSUMER_KEY", "CONSUMER_SECRET"]
access_token, access_secret, consumer_key, consumer_secret = [
        kms.decrypt(CiphertextBlob=b64decode(os.environ[env]))["Plaintext"].decode("utf8")
        for env in envs ]

oauth = OAuth(access_token, access_secret, consumer_key, consumer_secret)

t_upload = Twitter(domain="upload.twitter.com", auth=oauth)
t = Twitter(auth=oauth)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

opener = request.build_opener(
        request.HTTPSHandler(),
        request.HTTPCookieProcessor(cookiejar.CookieJar()))
request.install_opener(opener)

def upload_image_by_url(image_url):
    req = request.Request(image_url)
    res = request.urlopen(req)
    image = res.read()

    return t_upload.media.upload(media=image)["media_id_string"]

def format_post(header, text):
    r_joint = " (続"
    l_joint = "続) "
    joint_size = len(r_joint)
    content_size = TWEET_SIZE - len(header)

    if content_size >= len(text):
        return [header + text]

    posts = []
    while content_size < len(text):
        posts.append(header + text[0:content_size-joint_size] + r_joint)
        text = text[content_size-joint_size:]
    posts.append(header + l_joint + text)

    return posts


def crawl_ameba_now(ameba_id, current_entry_id, mitayo_flg):
    url = os.path.join(BASE_NOW_URL, ameba_id)
    logger.info(url)

    html = request.urlopen(url).read()
    soup = BeautifulSoup(html, "html.parser")

    posts = []
    for entry in soup.select("li.now"):
        entry_id = entry.get('data-entry-id')
        logger.info(entry_id)

        if entry_id == current_entry_id:
            break

        text = entry.select('.text')[0].string.strip()
        img_urls = [
            img.get('data-original-image') for img in entry.select('img')
        ]

        time_str = entry.select('.time')[0].string
        m = re.findall("(\d+)分前", time_str)

        if len(m) == 0:
            formatted_time = time_str
        else:
            ut = int(time.time()) - int(m[0])*60 - 10
            formatted_time = datetime.strftime(
                datetime.fromtimestamp(ut), "[%-m/%d %H:%M]"
            )

        header = formatted_time + " "
        posts.append({
            "entry_id": entry_id,
            "content": format_post(header, text),
            "img_urls": img_urls,
        })


    succeeded_entry_id = ""
    posts.reverse()
    while len(posts) > 0:
        post = posts.pop()

        for content in post["content"]:
            img_urls_per_tweet = post["img_urls"][:MAX_IMAGES_PER_TWEET]
            logger.info(content)
            logger.info(img_urls_per_tweet)

            if len(img_urls_per_tweet) > 0:
                post["img_urls"] = post["img_urls"][len(img_urls_per_tweet):]

                media_ids = [
                    upload_image_by_url(u) for u in img_urls_per_tweet
                ]
                logger.info(media_ids)
                res = t.statuses.update(
                    status=content, media_ids=",".join(media_ids)
                )
            else:
                res = t.statuses.update(status=content)

            logger.info(post["entry_id"])
            succeeded_entry_id = post["entry_id"]

    if len(succeeded_entry_id) > 0:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                "ameba_id": {"S": ameba_id}
            },
            UpdateExpression="SET blog_entry_id = :new_id",
            ExpressionAttributeValues={
                ":new_id": {"N": succeeded_entry_id}
            }
        )

def lambda_handler(event, context):
    items = dynamodb.scan(TableName=DYNAMODB_TABLE_NAME)

    for item in items["Items"]:
        crawl_ameba_now(
            item["ameba_id"]["S"],
            item["now_entry_id"]["N"],
            item["mitayo_flg"]["BOOL"]
        )

if __name__ == "__main__":
    lambda_handler(None, None)
