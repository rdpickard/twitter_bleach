import json
import time

import jsonschema

from wrapped_pytwitter_api import *

# Use version2 Twitter API to delete lists
#
# Lists owned by a user
# https://developer.twitter.com/en/docs/twitter-api/lists/list-lookup/api-reference/get-users-id-owned_lists
#
# List members endpoint
# https://developer.twitter.com/en/docs/twitter-api/lists/list-members/api-reference/get-lists-id-members
#
# Delete lists
# https://developer.twitter.com/en/docs/twitter-api/lists/manage-lists/api-reference/delete-lists-id
#
# For long runs, the code will refresh the authentication bearer token when it expires
#


def _archive_list_members(api, list_id, archive_file, list_members_schema):

    failed_requests_in_a_row = 0
    max_failed_requests_in_a_row = 5

    pagination_token = None

    while True:
        try:

            list_members_response = api.get_list_members(list_id=list_id,
                                                         pagination_token=pagination_token,
                                                         return_json=True)

            jsonschema.validate(list_members_response, list_members_schema)

            for list_member in list_members_response["data"]:
                archive_file.write("{},{},\"{}\",{}\n".format(
                    list_id,
                    list_member["id"],
                    list_member["name"].replace(',', '\,'),
                    list_member['username'].replace(',', '\,')
                ))

            if 'next_token' not in list_members_response['meta'].keys():
                break

            pagination_token = list_members_response['meta']['next_token']

        except WrappedPyTwitterAPIUnauthorizedException:
            logging.info("Authentication failed. Access token may have expired")
            api.refresh_access_token()
            continue
        except WrappedPyTwitterAPIServiceUnavailableException:
            failed_requests_in_a_row += 1
            if failed_requests_in_a_row < max_failed_requests_in_a_row:
                logging.info("API service unavailable. Waiting 5 seconds, resetting pagination and trying again")
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


def bleach_lists(api, list_limit=None, list_archive_csv_file=None, _dont_actually_bleach=False):
    """
    Delete lists owned by the user of the authenticated api object

    :param api: Instance of an authenticated pytwitter2 WrappedPyTwitterAPI
    :param list_limit: limit the number of lists to delete
    :param list_archive_csv_file: File object to write details of deleted lists to
    :param _dont_actually_bleach: boolean to not actually make DELETE API call. For testing. Default False
    :return: Number of lists deleted
    """

    twitter_me = api.get_me(return_json=True)
    twitter_user_id = twitter_me["data"]["id"]

    total_lists_deleted = 0

    pagination_token = None

    list_not_deleted = []

    failed_requests_in_a_row = 0
    max_failed_requests_in_a_row = 5

    with open("schemas/twitter_lists_endpoint_response_schema.json") as lists_response_schema_file:
        lists_json_schema = json.load(lists_response_schema_file)
    with open("schemas/twitter_lists_members_endpoint_response_schema.json") as lists_members_response_schema_file:
        lists_members_json_schema = json.load(lists_members_response_schema_file)

    while True:
        try:

            list_query_result = api.get_user_owned_lists(user_id=twitter_user_id,
                                                         pagination_token=pagination_token,
                                                         return_json=True)

            jsonschema.validate(lists_json_schema, list_query_result)

            for twitter_list in list_query_result["data"]:

                if list_archive_csv_file is not None:
                    list_archive_csv_file.write("LIST,{},\"{}\"\n".format(
                        twitter_list["id"],
                        twitter_list["name"].replace(",", "\,")
                    ))
                    _archive_list_members(api, twitter_list["id"], list_archive_csv_file, lists_members_json_schema)

                if not _dont_actually_bleach:
                    api.delete_list(twitter_list["id"])

            if 'next_token' not in list_query_result['meta'].keys():
                break

            pagination_token = list_query_result['meta']['next_token']

        except WrappedPyTwitterAPIUnauthorizedException:
            logging.info("Authentication failed. Access token may have expired")
            api.refresh_access_token()
            continue
        except WrappedPyTwitterAPIServiceUnavailableException:
            failed_requests_in_a_row += 1
            if failed_requests_in_a_row < max_failed_requests_in_a_row:
                logging.info("API service unavailable. Waiting 5 seconds, resetting pagination and trying again")
                list_not_deleted = []
                pagination_token = None
                time.sleep(5)
                continue
            else:
                logging.info("API service unavailable. Failed {} times in a row, max failed attempts {}. Bailing.".format(failed_requests_in_a_row, max_failed_requests_in_a_row))
                break
        except WrappedPyTwitterAPIRateLimitExceededException:
            logging.info("List members limit exceeded. Waiting 15min.")
            time.sleep(900)
            continue
        except pytwitter.error.PyTwitterError as ptw:
            logging.fatal("PyTwitterError with unknown message format '{}'".format(ptw.message['status'], ptw.message))
            break
        except Exception as e:
            logging.fatal("Exception of unhandled type {}. Message is '{}'".format(type(e), e))

