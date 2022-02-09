import logging
import json
import time

from wrapped_pytwitter_api import *

# Loop through all of the user tweets and delete them
# https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-tweets#Optional

def bleach_tweets(api, twitter_user_id, delete_limit=None):

    total_tweets_deleted = 0
    tweets_not_processed = []

    pagination_token = None

    while delete_limit is None or total_tweets_deleted <= delete_limit:
        try:
            user_tweets_query_result = api.get_timelines(user_id=twitter_user_id,
                                                         return_json=True,
                                                         max_results=50,
                                                         pagination_token=pagination_token)

            tweet_ids_to_delete = list(map(lambda t: t["id"], user_tweets_query_result['data']))

            logging.debug("List of user '{}' tweet IDs to delete from API {}".format(twitter_user_id,
                                                                                     tweet_ids_to_delete)
                          )
            logging.debug("List of user '{}' tweet IDs to delete residual from last run {}".format(twitter_user_id,
                                                                                                   tweets_not_processed)
                          )

            tweets_to_process = user_tweets_query_result['data'] + tweets_not_processed
            tweets_not_processed = []

            for tweet in tweets_to_process:
                logging.info("archive of tweet '{}'".format(json.dumps(tweet)))
                try:
                    if tweet['text'].startswith("RT "):
                        delete_response = api.remove_retweet_tweet(user_id=twitter_user_id, tweet_id=tweet["id"])
                    else:
                        delete_response = api.delete_tweet(tweet_id=tweet["id"])
                    logging.debug("Response to delete of tweet {} '{}'".format(tweet["id"], delete_response))
                    total_tweets_deleted += 1

                except WrappedPyTwitterAPIRateLimitExceededException:
                    # NOTE There is a rate limit of 50 'delete tweet' per 15 min window
                    # https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/delete-tweets-id
                    tweets_not_processed.append(tweet)
                    logging.info(
                        "Unlike Tweet rate limit exceeded. Waiting 15min. Deleted so far {}".format(
                            total_tweets_deleted))
                    time.sleep(900)
                    continue

            if 'next_token' not in user_tweets_query_result['meta'].keys():
                break

            pagination_token = user_tweets_query_result['meta']['next_token']

        except WrappedPyTwitterAPIUnauthorizedException:
            logging.info("Authentication failed. Access token may have expired")
            api.refresh_access_token()
            continue
        except pytwitter.error.PyTwitterError as ptw:
            logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
            break

    logging.debug(f"Total deleted {total_tweets_deleted}")
