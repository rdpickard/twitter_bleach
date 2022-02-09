import base64
import logging
import json
import time

from wrapped_pytwitter_api import *

# Use version2 Twitter API to unlike tweets
# https://developer.twitter.com/en/docs/twitter-api/tweets/likes/api-reference/delete-users-id-likes-tweet_id
#
# The API has a ratelimit of 50 unlikes requests per 15 min. Code will pause if rate limit is exceeded and
# then continue.
#
# For long runs, the code will refresh the authentication bearer token when it expires
#


def bleach_likes(api, unlike_limit=None, likes_archive_file=None, _dont_actually_bleach=False):
    """
    Unlike all the tweets a user has liked in their timeline

    :param api: Instance of an authenticated pytwitter2 WrappedPyTwitterAPI
    :param unlike_limit: Limit of tweets to unlike. Default is None, which will unlike all
    :param likes_archive_file: File to archive details of unliked tweets. Default is None, which is no archiving
    :param _dont_actually_bleach: boolean to not actually make DELETE API call. For testing. Default False
    :return: Number of tweets unliked
    """

    twitter_me = api.get_me(return_json=True)
    twitter_user_id = twitter_me["data"]["id"]

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
    return total_unliked_tweets
