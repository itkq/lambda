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

BASE_BLOG_URL = "http://ameblo.jp"
SEARCH_LIMIT_INDEX = 1
DYNAMODB_TABLE_NAME = "AmebaCrawling"

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

def get_new_articles(ameba_id, current_entry_id, page):
    url = os.path.join(BASE_BLOG_URL, ameba_id, "page-%s.html" % page)
    logger.info(url)

    html = request.urlopen(url).read()
    soup = BeautifulSoup(html, "html.parser")

    new_articles = []
    fetched_articles = soup.select(".skinArticle")

    for article in fetched_articles:
        title = article.select(".skinArticleTitle")[0].string.strip()
        url = article.select(".skinArticleTitle")[0].get("href")
        entry_id = re.search(r"entry-(\d+)\.html", url).group(1)
        img_urls = [ i.get("src") for i in article.select(".detailOn > img")
                if re.search("\.(jpg|png)", i.get("src")) ]

        if entry_id == current_entry_id:
            break

        new_articles.append({
            "title": title,
            "url": url,
            "entry_id": entry_id,
            "img_urls": img_urls})

    is_continued = len(new_articles) == len(fetched_articles)

    return (is_continued, new_articles)

def crawl_ameblo(ameba_id, blog_entry_id, iine_flg):
    target_articles = []
    for page in range(1, SEARCH_LIMIT_INDEX+1):
        is_continued, new_articles = get_new_articles(
            ameba_id, blog_entry_id, page)

        target_articles.extend(new_articles)

        if not is_continued:
            break

    for article in reversed(target_articles):
        media_ids = [ upload_image_by_url(u) for u in article["img_urls"] ]
        tweet_content = "『%s』⇒\n%s" % (article["title"], article["url"])

        logger.info(media_ids)
        logger.info(tweet_content)

        if len(media_ids) > 0:
            logger.info(tweet_content)
            logger.info(media_ids)
            res = t.statuses.update(status=tweet_content, media_ids=",".join(media_ids))
        else:
            logger.info(tweet_content)
            res = t.statuses.update(status=tweet_content)

        logger.info(res)


    logger.info(target_articles)

    if len(target_articles) > 0:
        logger.info(target_articles[0])
        new_entry_id = target_articles[0]["entry_id"]
        dynamodb.update_item(
                TableName=DYNAMODB_TABLE_NAME,
                Key={
                    "ameba_id": {
                        "S": ameba_id
                        }
                    },
                UpdateExpression="SET blog_entry_id = :new_id",
                ExpressionAttributeValues={
                    ":new_id": {
                        "N": new_entry_id
                        }
                    }
                )


def lambda_handler(event, context):
    items = dynamodb.scan(TableName=DYNAMODB_TABLE_NAME)
    logger.info(items)
    for item in items["Items"]:
        crawl_ameblo(
                item["ameba_id"]["S"],
                item["blog_entry_id"]["N"],
                item["iine_flg"]["BOOL"])

if __name__ == "__main__":
    lambda_handler(None, None)
