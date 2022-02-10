import os
import logging
import sys
import time
import json
import base64

from wrapped_pytwitter_api import *
from bleach_twitter_likes import *
from bleach_twitter_tweets import *
from bleach_twitter_follows import *

if sys.version_info < (3, 7):
    # script uses functools.partial which is a pretty recent capability
    print("Python 3.7 or later required to run")
    sys.exit(-1)

LOCAL_HTTPD_SERVER_PORTS_TO_TRY = [8888, 8880, 8080, 9977, 4356, 3307]

TWITTER_CLIENT_ID = os.environ.get("TWITTER_CLIENT_ID")

# P Change this value to log output to a file
logging_file_name = "local/like-unlike.log"

logging.basicConfig(
    filename=logging_file_name,
    format='%(asctime)s %(name)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')

BLEACH_FOLLOWS = True
BLEACH_LIKES = False
BLEACH_TWEETS = False

# The scopes requested of the Twitter OAUTH2 API on behalf of the user that will bleach their account
twitter_api_scopes = ["tweet.read", "tweet.write", "users.read", "tweet.read",
                      "users.read", "like.write", "like.read", "follows.read",
                      "follows.write", "offline.access"]


api = WrappedPyTwitterAPI(client_id=TWITTER_CLIENT_ID, oauth_flow=True, scopes=twitter_api_scopes)
auth_details = api.OAuth2AuthenticationFlowHelper(local_ports_to_try=LOCAL_HTTPD_SERVER_PORTS_TO_TRY)
logging.info(f"Twitter OAuth2 details '{auth_details}'")

# Get details about the account. Specifically the Twitter ID for the user that authorized the app.
twitter_me = api.get_me(return_json=True)
my_twitter_id = twitter_me["data"]["id"]

if BLEACH_LIKES:
    bleach_likes(api)

if BLEACH_TWEETS:
    bleach_tweets(api)

if BLEACH_FOLLOWS:
    follows_archive = open("local/follows_archive.csv", "a+")
    unfollows = bleach_follows(api, follows_archive_csv_file=follows_archive, _dont_actually_bleach=True)
