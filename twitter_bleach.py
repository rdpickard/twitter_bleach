import os
import http.server
import logging
import sys

import pytwitter

LOCAL_HTTPD_SERVER_PORTS_TO_TRY = [8888, 8880, 8080, 9977, 4356, 3307]

TWITTER_CLIENT_ID = os.environ.get("TWITTER_CLIENT_ID")

auth_url = ""

logging.basicConfig(level=logging.DEBUG)

BLEACH_FOLLOWS = True
BLEACH_LIKES = True
BLEACH_TWEETS = True

# The scopes requested of the Twitter OAUTH2 API on behalf of the user that will bleach their account
twitter_api_scopes = ["tweet.read", "tweet.write", "users.read", "tweet.read",
                      "users.read", "like.write", "like.read", "follows.read",
                      "follows.write"]


class SuperSimpleRequestHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        global auth_url
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")
        # TODO Return a message to say something like "OK! go back to the CLI app!"
        auth_url = self.path
        return self


# Start a minimal local HTTPD listener to get the authorization details.
# When the Twitter OAUTH2.0 process redirects the local HTTPD listener will get the request. This way the user
# doesn't have to copy and paste strings or anything like that
httpd_bound_port = None
httpd = None
for httpd_bound_port in LOCAL_HTTPD_SERVER_PORTS_TO_TRY:
    try:
        httpd = http.server.HTTPServer(('', httpd_bound_port), SuperSimpleRequestHandler)
        break
    except Exception as e:
        logging.info(f"Could not start http listener on port '{httpd_bound_port}'")

if httpd is None:
    logging.fatal(f"Could not start http listener on any port '{LOCAL_HTTPD_SERVER_PORTS_TO_TRY}'. Exiting")
    sys.exit(-1)
else:
    logging.debug(f"HTTPD listening on port {httpd_bound_port}")

twitter_auth_callback_redirect_url = f"http://127.0.0.1:{httpd_bound_port}/"

# Start the OAUTH2 process with Twitter to get a temporary bearer token that authorizes making changes to the
# account.
api = pytwitter.Api(client_id=TWITTER_CLIENT_ID, oauth_flow=True,
                    scopes=['block.read', "users.read", "tweet.read", "follows.read", "follows.write"])
twitter_user_auth_url, code_verifier, _ = api.get_oauth2_authorize_url(redirect_uri=twitter_auth_callback_redirect_url)
print("CLICK ME \u2193\u2193\u2193\u2193")
print(twitter_user_auth_url)
print()

# This should wait forever until the user clicks "Authorize App" after following the twitter_user_auth_url above
httpd.handle_request()

# Using the 'state' and 'code' values in the redirect URL that the Twitter OAUTH 2 calls, request a bearer token
# for the user context. The user context is what lets this script make changes on behalf of the user that
# "Authorized App"
auth_details = api.generate_oauth2_access_token(auth_url, code_verifier,
                                                redirect_uri=twitter_auth_callback_redirect_url)

# I think it's there is a bug in 'pytwitter'. Need to create a second API instance with the bearer token for user
# context to work
api2 = pytwitter.Api(bearer_token=auth_details['access_token'])

# Get details about the account. Specifically the Twitter ID for the user that authorized the app.
twitter_me = api2.get_me(return_json=True)
logging.debug(twitter_me)

# Loop through all of the followers and unfollow them
cursor_token = None
total_following = 0
while BLEACH_FOLLOWS:
    following_query_result = api2.get_following(user_id=twitter_me["data"]["id"], return_json=True, pagination_token=cursor_token)

    for followed_user in following_query_result['data']:
        total_following += 1
        # NOTE There is a rate limit of 50 'unfollow' per 15-min window https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/delete-users-source_id-following
        # TODO Unfollow here

    if "next_token" not in following_query_result["meta"].keys() or len(following_query_result['data']) < 1:
        break
    cursor_token = following_query_result['meta']['next_token']
logging.debug(f"Total follows count {total_following}")

# Loop through all of the likes and unlike them
total_likes = 0
while BLEACH_LIKES:
    break
    # NOTE There is a rate limit of 75 requests for likes per 15-min window https://developer.twitter.com/en/docs/twitter-api/tweets/likes/api-reference/get-users-id-liked_tweets
    # NOTE There is a rate limit of 50 'unlikes' per 15-min window https://developer.twitter.com/en/docs/twitter-api/tweets/likes/api-reference/delete-users-id-likes-tweet_id
logging.debug(f"Total likes {total_likes}")


# Loop through all of the user tweets and delete them
total_tweets = 0
while BLEACH_TWEETS:
    break
    # NOTE There is a rate limit of 50 'delete tweet' per 15 min window https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/delete-tweets-id
logging.debug(f"Total likes {total_tweets}")

print(total_following)
