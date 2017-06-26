#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from bs4 import BeautifulSoup
from urllib import request
from http import cookiejar
from twitter import *
import logging

BASE_BLOG_URL = "http://ameblo.jp"
SEARCH_LIMIT_INDEX = 3

oauth = OAuth(
        os.environ["ACCESS_TOKEN"],
        os.environ["ACCESS_SECRET"],
        os.environ["CONSUMER_KEY"],
        os.environ["CONSUMER_SECRET"])

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

def crawl_ameblo(info):
    target_articles = []
    for page in range(1, SEARCH_LIMIT_INDEX+1):
        is_continued, new_articles = get_new_articles(
            info["ameba_id"], info["blog_entry_id"], page)

        target_articles.extend(new_articles)

        if not is_continued:
            break

    for article in reversed(target_articles):
        media_ids = [ upload_image_by_url(u) for u in article["img_urls"] ]
        tweet_content = "『%s』⇒\n%s" % (article["title"], article["url"])

        logger.info(media_ids)
        logger.info(tweet_content)

        if len(media_ids) > 0:
            t.statuses.update(status=tweet_content, media_ids=",".join(media_ids))
        else:
            t.statuses.update(status=tweet_content)

def main():
    # read from yml

    articles = [
            {
                "ameba_id": "ari-step",
                "now_entry_id": "",
                "blog_entry_id": "12286307930",
                "iine": False,
                "mitayo": True,
                }
            ]

    for article in articles:
        crawl_ameblo(article)

if __name__ == "__main__":
    main()
