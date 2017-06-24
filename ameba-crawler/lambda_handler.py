# -*- coding: utf-8 -*-

import os
import re
from bs4 import BeautifulSoup
from twython import Twython
import cookielib
import urllib2

twitter = Twython(
        os.environ['CONSUMER_KEY'],
        os.environ['CONSUMER_SECRET'],
        os.environ['ACCESS_TOKEN'],
        os.environ['ACCESS_SECRET'])

BASE_BLOG_URL = "http://ameblo.jp"
MAX_INDEX = 5

opener = urllib2.build_opener(urllib2.HTTPSHandler(debuglevel=1),
        urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
urllib2.install_opener(opener)

def get_new_articles(ameba_id, current_entry_id, page):
    url = os.path.join(BASE_BLOG_URL, ameba_id, "page-%s.html" % page)
    print(url)

    html = urlopen(url).read()
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
            "img_urls": img_urls
            })

    is_continued = len(new_articles) == len(fetched_articles)

    return (is_continued, new_articles)

def upload_media_by_url(image_url):
    req = urllib2.Request(image_url)
    res = urllib2.urlopen(req)
    image = res.read()

    ret = twitter.upload_media(media=image)
    print(ret)

def crawl_ameblo(info):
    # target_articles = []
    # for page in range(1, MAX_INDEX+1):
    #     is_continued, new_articles = get_new_articles(
    #             info["ameba_id"], info["blog_entry_id"], page
    #             )
    #
    #     target_articles.extend(new_articles)
    #
    #     if not is_continued:
    #         break
    #
    # print(target_articles)

    target_articles = [{
        'url': 'http://ameblo.jp/ari-step/entry-12286307930.html',
        'img_url': ['https://stat.ameba.jp/user_images/20170622/15/ari-step/bb/67/j/o0640048013966365231.jpg?caw=800', 'https://stat.ameba.jp/user_images/20170622/15/ari-step/5f/c6/j/o0800059913966365239.jpg?caw=800', 'https://stat.ameba.jp/user_images/20170622/15/ari-step/c9/c7/j/o0640036013966365264.jpg?caw=800'],
        'entry_id': '12285500282', # 12286307930
        'title': '飲み'
        }]

    print(target_articles)

    for article in reversed(target_articles):
        tweet_content = "%s %s" % (article['title'], article['url'])



def main():
    articles = [
            {
                "ameba_id": "ari-step",
                "now_entry_id": "",
                "blog_entry_id": "12285500282",
                "iine": False,
                "mitayo": True,
                }
            ]

    for article in articles:
        crawl_ameblo(article)

if __name__ == "__main__":
    main()
