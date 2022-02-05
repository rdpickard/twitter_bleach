import base64
import logging
import json
import time

from wrapped_pytwitter_api import *


# https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/delete-users-source_id-following


def bleach_follows(api, twitter_user_id, unfollow_limit=None):

    total_users_unfollowed = 0

    pagination_token = None

    users_not_unfollowed = []

    while unfollow_limit is None or unfollow_limit <= total_users_unfollowed:
        try:
            following_query_result = api.get_following(user_id=twitter_user_id,
                                                       return_json=True,
                                                       pagination_token=pagination_token)

            user_ids_to_unfollow = list(map(lambda t: t["id"], following_query_result['data']))

            for followed_user_id in user_ids_to_unfollow:
                try:
                    # TODO Unfollow here
                    unfollow_response = api.unfollow_user(twitter_user_id, followed_user_id)
                    total_users_unfollowed += 1

                except WrappedPyTwitterAPIRateLimitExceededException:
                    users_not_unfollowed.append(followed_user_id)
                    logging.info(
                        "Unfollow Twitter user rate limit exceeded. Waiting 15min. Unfollowed so far {}".format(
                            total_users_unfollowed))
                    time.sleep(900)
                    continue

            if 'next_token' not in following_query_result['meta'].keys():
                break

            pagination_token = following_query_result['meta']['next_token']

        except WrappedPyTwitterAPIUnauthorizedException:
            logging.info("Authentication failed. Access token may have expired")
            api.refresh_access_token()
            continue
        except pytwitter.error.PyTwitterError as ptw:
            logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
            break

    logging.debug(f"Total follows count {total_users_unfollowed}")

