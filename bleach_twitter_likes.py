import base64
import logging
import json
import time

from wrapped_pytwitter_api import *


def bleach_likes(api, twitter_user_id, unlike_limit=None):

    previous_likes_file_handle = open("local/previous_likes.txt", 'a+')

    total_unliked_tweets = 0

    tweet_ids_not_done = []
    pagination_token = None

    while unlike_limit is None or total_unliked_tweets <= unlike_limit:
        try:
            liked_tweets_query_result = api.get_user_liked_tweets(user_id=twitter_user_id,
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
                    api.like_tweet(twitter_user_id, tweet_id=tweet_id)
                    time.sleep(2)
                    api.unlike_tweet(twitter_user_id, tweet_id=tweet_id)
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
            api.refresh_access_token()
            continue
        except pytwitter.error.PyTwitterError as ptw:
            logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
            break

    logging.debug(f"Total likes {total_unliked_tweets}")
    previous_likes_file_handle.close()
