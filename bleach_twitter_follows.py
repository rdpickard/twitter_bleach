import base64
import logging
import json
import time

import jsonschema

from wrapped_pytwitter_api import *

# Use version2 Twitter API to unfollow users
# https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/delete-users-source_id-following
#
# The API has a ratelimit of 50 unfollow requests per 15 min. Code will pause if rate limit is exceeded and
# then continue.
#
# For long runs, the code will refresh the authentication bearer token when it expires
#


def bleach_follows(api, unfollow_limit=None, follows_archive_csv_file=None, _dont_actually_bleach=False):
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

    failed_requests_in_a_row = 0
    max_failed_requests_in_a_row = 5

    with open("schemas/twitter_followers_endpoint_response_schema.json") as response_schema_file:
        followers_json_schema = json.load(response_schema_file)

    while unfollow_limit is None or total_users_unfollowed <= unfollow_limit:

        try:
            following_query_result = api.get_following(user_id=twitter_user_id,
                                                       return_json=True,
                                                       pagination_token=pagination_token)

            jsonschema.validate(following_query_result, followers_json_schema)
            failed_requests_in_a_row = 0

            users_to_unfollow = following_query_result["data"]+users_not_unfollowed

            for followed_user in users_to_unfollow:
                if unfollow_limit is not None and total_users_unfollowed > unfollow_limit:
                    break

                try:
                    # TODO Unfollow here
                    if not _dont_actually_bleach:
                        unfollow_response = api.unfollow_user(twitter_user_id, followed_user["id"])
                    total_users_unfollowed += 1
                    if follows_archive_csv_file is not None:
                        follows_archive_csv_file.write("{},\"{}\",{}\n".format(
                            followed_user['id'],
                            followed_user['name'].replace(',', '\,'),
                            followed_user['username'].replace(',', '\,')
                        ))

                except WrappedPyTwitterAPIRateLimitExceededException:
                    users_not_unfollowed.append(followed_user)
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
        except WrappedPyTwitterAPIServiceUnavailableException:
            failed_requests_in_a_row += 1
            if failed_requests_in_a_row < max_failed_requests_in_a_row:
                logging.info("API service unavailable. Waiting 5 seconds, resetting pagination and trying again")
                users_not_unfollowed = []
                pagination_token = None
                time.sleep(5)
                continue
            else:
                logging.info("API service unavailable. Failed {} times in a row, max failed attempts {}. Bailing.".format(failed_requests_in_a_row, max_failed_requests_in_a_row))
                break
        except pytwitter.error.PyTwitterError as ptw:
            logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
            break
        except Exception as e:
            logging.fatal("Exception of unhandled type {}. Message is '{}'".format(type(e), e))


    logging.debug(f"Total unfollows count {total_users_unfollowed}")
    return total_users_unfollowed
