import base64
import logging
import json
import time

from wrapped_pytwitter_api import *

# Use version2 Twitter API to unfollow users
# https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/delete-users-source_id-following
#
# The API has a ratelimit of 50 unfollow requests per 15 min. Code will pause if rate limit is exceeded and
# then continue.
#
# For long runs, the code will refresh the authentication bearer token when it expires
#


def bleach_follows(api, unfollow_limit=None, follows_archive_file=None, _dont_actually_bleach=False):
    """
    Unfollow users for the user specified by the passed in ID.

    :param api: Instance of an authenticated pytwitter2 WrappedPyTwitterAPI
    :param unfollow_limit: Limit of unfollows. Default is None, will attempt to unfollow all
    :param follows_archive_file: File to write details of unfollowed user. Default is None
    :param _dont_actually_bleach: boolean to not actually make DELETE API call. For testing. Default False
    :return: Number of unfollowed accounts
    """

    twitter_me = api.get_me(return_json=True)
    twitter_user_id = twitter_me["data"]["id"]

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
    return total_users_unfollowed
