# http://qiita.com/onoxeve/items/0c843d97c8db0e7f3feb
# coding:utf-8

from __future__ import print_function

import boto3
import json
import logging
import os
import datetime

from base64 import b64decode
from urllib2 import Request, urlopen, URLError, HTTPError

# The base-64 encoded, encrypted key (CiphertextBlob) stored in the kmsEncryptedHookUrl environment variable
ENCRYPTED_HOOK_URL = os.environ['kmsEncryptedHookUrl']

HOOK_URL = boto3.client('kms').decrypt(CiphertextBlob=b64decode(ENCRYPTED_HOOK_URL))['Plaintext']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CloudWatchからAWS請求情報を取得(昨日から今日にかけて1日分の最大値)
# 2017/7現在: バージニア北部(us-east-1)リージョンのみ請求情報を取得可能
cloud_watch = boto3.client('cloudwatch', region_name='us-east-1')
get_metric_statistics = cloud_watch.get_metric_statistics(
    Namespace='AWS/Billing',
    MetricName='EstimatedCharges',
    Dimensions=[{
        'Name': 'Currency',
        'Value': 'USD'
    }],
    StartTime=datetime.datetime.today() - datetime.timedelta(days=1),
    EndTime=datetime.datetime.today(),
    Period=86400,
    Statistics=['Maximum']
)

def lambda_handler(event, context):
    logger.info("Event: " + str(event))
    #message = json.loads(event['Records'][0]['Sns']['Message'])

    # AWS請求情報をフィルタ1
    message = get_metric_statistics['Datapoints'][0]
    logger.info("Message: " + str(message))

    #alarm_name = message['AlarmName']
    #old_state = message['OldStateValue']
    #new_state = message['NewStateValue']
    #reason = message['NewStateReason']

    # AWS請求情報をフィルタ2
    currency_statistics = message['Maximum']
    time_statistics = message['Timestamp'].strftime('%Y/%m/%d')

    # しきい値超過でSlackメッセージの色を変更する
    if currency_statistics > 15.0:
        notify_color = "danger"
    else:
        notify_color = "good"

    # Slack投稿メッセージ
    # username,color,title,title_linkを追加
    slack_message = {
        'attachments': [{
            # メッセージを色分けする
            'color': notify_color,
            # タイトルを追加
            "title": "AWS Billing & Cost",
            # AWS請求ダッシュボードへのリンクを設定
            "title_link": "https://console.aws.amazon.com/billing/home?#/",
            # メッセージ本文
            'text': "EstimatedCharges is now %s USD in %s" % (currency_statistics, time_statistics)
        }]
    }
    logger.info(slack_message)

    req = Request(HOOK_URL, json.dumps(slack_message))
    response = urlopen(req)
    logger.info(response.read())
