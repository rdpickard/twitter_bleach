import os
import logging
import sys
import time
import json
import base64

from wrapped_pytwitter_api import *

if sys.version_info < (3, 7):
    # script uses functools.partial which is a pretty recent capability
    print("Python 3.7 or later required to run")
    sys.exit(-1)

LOCAL_HTTPD_SERVER_PORTS_TO_TRY = [8888, 8880, 8080, 9977, 4356, 3307]

TWITTER_CLIENT_ID = os.environ.get("TWITTER_CLIENT_ID")

# P Change this value to log output to a file
logging_file_name = None

logging.basicConfig(
    filename=logging_file_name,
    format='%(asctime)s %(name)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')

BLEACH_FOLLOWS = False
BLEACH_LIKES = True
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

# Loop through all of the followers and unfollow them
cursor_token = None
total_following = 0
while BLEACH_FOLLOWS:
    following_query_result = api.get_following(user_id=twitter_me["data"]["id"],
                                               return_json=True,
                                               pagination_token=cursor_token)

    for followed_user in following_query_result['data']:
        total_following += 1
        # NOTE There is a rate limit of 50 'unfollow' per 15-min window https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/delete-users-source_id-following
        # TODO Unfollow here

    if "next_token" not in following_query_result["meta"].keys() or len(following_query_result['data']) < 1:
        break
    cursor_token = following_query_result['meta']['next_token']
logging.debug(f"Total follows count {total_following}")

# Loop through all of the likes and unlike them
total_unliked_tweets = 0
pagination_token = None

previous_likes_file_handle = open("local/previous_likes.txt", 'a+')
tweet_ids_not_done = []
while BLEACH_LIKES:
    try:
        liked_tweets_query_result = api.get_user_liked_tweets(user_id=twitter_me["data"]["id"],
                                                              return_json=True,
                                                              max_results=50,
                                                              pagination_token=pagination_token)

        if 'data' not in liked_tweets_query_result.keys():
            logging.warning("Twitter response to liked data has no key 'data'. Skipping. Response JSON '{}'".format(base64.b64encode(json.dumps(liked_tweets_query_result).encode())))
            continue

        tweet_ids_to_do = list(map(lambda t: t["id"], liked_tweets_query_result['data']))

        logging.debug("List of liked tweet IDs from API {}".format(tweet_ids_to_do))
        logging.debug("List of liked tweet IDs residual from last run {}".format(tweet_ids_not_done))

        tweet_ids_to_do = tweet_ids_not_done + tweet_ids_to_do

        tweet_ids_not_done = []
        for tweet_id in tweet_ids_to_do:
            try:
                api.unlike_tweet(my_twitter_id, tweet_id=tweet_id)
                total_unliked_tweets += 1
            except WrappedPyTwitterAPIRateLimitExceededException:
                tweet_ids_not_done.append(tweet_id)
                logging.info(
                    "Unlike Tweet rate limit exceeded. Waiting 15min. Unliked so far {}".format(total_unliked_tweets))
                time.sleep(900)
                continue

        if 'next_token' not in liked_tweets_query_result['meta'].keys():
            break

        pagination_token = liked_tweets_query_result['meta']['next_token']

    except WrappedPyTwitterAPIUnauthorizedException:
        logging.info("Authentication failed. Access token may have expired")
        auth_details = api.refresh_access_token(auth_details["refresh_token"])
        continue
    except pytwitter.error.PyTwitterError as ptw:
        logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
        break

logging.debug(f"Total likes {total_unliked_tweets}")
previous_likes_file_handle.close()

# Loop through all of the user tweets and delete them
# https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-tweets#Optional
total_tweets_bleached = 0
tweets_not_processed = []
pagination_token = None
max_tweets_to_process = 5
while BLEACH_TWEETS and (max_tweets_to_process == -1 or total_tweets_bleached < max_tweets_to_process):
    try:
        user_tweets_query_result = api.get_timelines(user_id=my_twitter_id,
                                                     return_json=True,
                                                     max_results=50,
                                                     pagination_token=pagination_token)

        tweet_ids_to_delete = list(map(lambda t: t["id"], user_tweets_query_result['data']))
        logging.info(f"Tweets IDs to delete for user '{my_twitter_id}' {tweet_ids_to_delete}")

        tweets_to_process = user_tweets_query_result['data'] + tweets_not_processed
        tweets_not_processed = []

        for tweet in tweets_to_process:
            logging.info("archive of tweet '{}'".format(json.dumps(tweet)))
            try:
                if tweet['text'].startswith("RT "):
                    delete_response = api.remove_retweet_tweet(user_id=my_twitter_id, tweet_id=tweet["id"])
                else:
                    delete_response = api.delete_tweet(tweet_id=tweet["id"])
                total_tweets_bleached += 1
                logging.info("Response of delete tweet '{}' -> '{}'".format(tweet["id"], delete_response))

            except WrappedPyTwitterAPIRateLimitExceededException:
                # NOTE There is a rate limit of 50 'delete tweet' per 15 min window https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/delete-tweets-id
                # This is why get_timelines has max_results of 50
                tweets_not_processed.append(tweet)
                logging.info(
                    "Unlike Tweet rate limit exceeded. Waiting 15min. Deleted so far {}".format(total_tweets_bleached))
                time.sleep(900)
                continue

        if 'next_token' not in user_tweets_query_result['meta'].keys():
            break

        pagination_token = user_tweets_query_result['meta']['next_token']

    except WrappedPyTwitterAPIUnauthorizedException:
        logging.info("Authentication failed. Access token may have expired")
        auth_details = api.refresh_access_token(auth_details["refresh_token"])
        continue
    except pytwitter.error.PyTwitterError as ptw:
        logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
        break

logging.debug(f"Total deleted {total_tweets_bleached}")
