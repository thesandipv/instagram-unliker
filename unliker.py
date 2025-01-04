import codecs
import json
import os
import sys
import datetime
from time import sleep
from instagram_private_api import (Client, ClientError, ClientTwoFactorRequiredError,
                                   ClientCookieExpiredError,  ClientLoginRequiredError, ClientLoginError,
                                   __version__ as client_version)

# =======================================

if len(sys.argv) > 2 and sys.argv[2] != None:
    like_removal_amount = int(sys.argv[2])
else:
    like_removal_amount = int(input(f"Enter unlike count:"))

if len(sys.argv) > 1 and sys.argv[1] != None:
    filter_username = sys.argv[1]
else:
    filter_username = input(
        f"Enter username, Enter N to delete likes of all posts. [USERNAME/N]:")
    if filter_username == "N":
        filter_username = None

quiet_mode = False
username = "YOUR_USERNAME"
password = "YOUR_PASSWORD"

# =======================================

output = ""


class Unliker:
    def to_json(self, python_object):
        if isinstance(python_object, bytes):
            return {'__class__': 'bytes',
                    '__value__': codecs.encode(python_object, 'base64').decode()}
        raise TypeError(repr(python_object) + ' is not JSON serializable')

    def from_json(self, json_object):
        if '__class__' in json_object and json_object['__class__'] == 'bytes':
            return codecs.decode(json_object['__value__'].encode(), 'base64')
        return json_object

    def on_login_callback(self, api, new_settings_file):
        cache_settings = api.settings
        with open(new_settings_file, 'w') as outfile:
            json.dump(cache_settings, outfile, default=self.to_json)
            println("SAVED: {0!s}".format(new_settings_file))

    def login(self, api: Client):
        try:
            println("Logging in via username and password...")
            api.login()
            println("Login successful.")
        except ClientTwoFactorRequiredError as e:
            println("Login failed, requiring 2FA!")
            response = json.loads(e.error_response)
            two_factor_info = response["two_factor_info"]
            phone_number_tail = two_factor_info["obfuscated_phone_number"]
            two_factor_identifier = two_factor_info['two_factor_identifier']
            verification_code = input(
                f"Verification code of authenticator or SMS (phone number ****{phone_number_tail}): ")
            try:
                println("Logging in again with 2FA...")
                api.login2fa(
                    two_factor_identifier, verification_code)
                println("Login with 2FA successful.")
            except ClientError as e:
                println("Login with 2FA failed as well.")
                println(e.error_response)
                print(output)
                exit()

    def __init__(self):
        print('Client version: {0!s}'.format(client_version))
        device_id = None
        settings_file = "settings.json"

        try:
            if not os.path.isfile(settings_file):
                println("Settings file not found, creating new one...")
                self.api = Client(
                    username, password, on_login=lambda x: self.on_login_callback(x, settings_file))

                self.login(self.api)
            else:
                with open(settings_file) as file_data:
                    cached_settings = json.load(
                        file_data, object_hook=self.from_json)
                println("Reusing settings...")
                device_id = cached_settings.get('device_id')
                self.api = Client(username, password, settings=cached_settings)
        except (ClientCookieExpiredError, ClientLoginRequiredError) as e:
            print(
                'ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e))
            # Login expired
            # Do relogin but use default ua, keys and such
            self.api = Client(
                username, password,
                device_id=device_id,
                on_login=lambda x: self.on_login_callback(x, settings_file))

            self.login(self.api)

        except ClientLoginError as e:
            print('ClientLoginError {0!s}'.format(e))
            exit(9)
        except ClientError as e:
            print('ClientError {0!s} (Code: {1:d}, Response: {2!s})'.format(
                e.msg, e.code, e.error_response))
            exit(9)
        except Exception as e:
            print('Unexpected Exception: {0!s}'.format(e))
            exit(99)

        # Show when login expires
        cookie_expiry = self.api.cookie_jar.auth_expires
        print('Cookie Expiry: {0!s}'.format(datetime.datetime.fromtimestamp(
            cookie_expiry).strftime('%Y-%m-%dT%H:%M:%SZ')))

    def unlike(self, remove_count, username):
        removed = 0
        liked = self.api.feed_liked()

        while removed < remove_count:
            count_reached = False
            next_max_id = liked['next_max_id']
            println(f"Next Max Id: {next_max_id}")

            if username != None:
                println(f"Beginning deletion of liked posts of {username}")

                for p in liked['items']:
                    post_id = p['id']

                    try:
                        if (p['user']['username']) == username:
                            self.api.delete_like(post_id)
                            removed += 1
                            println(f"{removed}: Deleted {post_id} by {
                                    p['user']['username']}")
                    except Exception as e:
                        println(
                            "\nRate limit most likely reached. Try again soon.")
                        println(f"Deleted {removed} liked posts.")
                        println("Exception: ")
                        println(e)
                        print(output)
                        return

                    if removed >= remove_count:
                        count_reached = True
                        break
            else:
                println(f"Beginning deletion of liked posts...")

                for p in liked['items']:
                    post_id = p['id']

                    try:
                        self.api.delete_like(post_id)
                        removed += 1
                        println(f"{removed}: Deleted {post_id} by {
                            p['user']['username']}")
                    except Exception as e:
                        println(
                            "\nRate limit most likely reached. Try again soon.")
                        println(f"Deleted {removed} liked posts.")
                        println("Exception: ")
                        println(e)
                        print(output)
                        return

                    if removed >= remove_count:
                        count_reached = True
                        break

            if not count_reached:
                println("Grabbing more posts...")
                sleep(1)

                while True:
                    liked = self.api.feed_liked(max_id=next_max_id)
                    if liked['status'] == 'ok':
                        break

                result_count = liked['num_results']
                println(f"Grabbed {result_count} more posts.")
                if result_count == 0:
                    print("No more posts to unlike.")
                    print(f"Deleted {removed} liked posts.")
                    break

        print(f"Finished deleting {removed} liked posts.")


def println(line):
    if quiet_mode:
        global output
        output += f"\n{line}"
    else:
        print(line)


print(f"Starting script to delete {like_removal_amount} likes...")
unliker = Unliker()
unliker.unlike(like_removal_amount, filter_username)
