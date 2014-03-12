"""
Functions in support of generating formatted digest emails of forums activity.
"""
from base64 import urlsafe_b64encode, urlsafe_b64decode
from hashlib import sha256
import logging
import sys

from Crypto.Cipher import AES
from Crypto import Random
from dogapi import dog_stats_api
from django.conf import settings
import requests


logger = logging.getLogger(__name__)


DIGEST_NOTIFICATION_PREFERENCE_KEY = 'notification_pref'
LANGUAGE_PREFERENCE_KEY = 'pref-lang'


class UserServiceException(Exception):
    pass

def _headers():
    return {'X-EDX-API-Key': settings.US_API_KEY}

def _auth():
    auth = {}
    if settings.US_HTTP_AUTH_USER:
        auth['auth'] = (settings.US_HTTP_AUTH_USER, settings.US_HTTP_AUTH_PASS)
    return auth

def _http_get(*a, **kw):
    try:
        logger.debug('GET {} {}'.format(a[0], kw))
        response = requests.get(*a, **kw)
    except requests.exceptions.ConnectionError, e:
        _, msg, tb = sys.exc_info()
        raise UserServiceException, "request failed: {}".format(msg), tb
    if response.status_code == 500:
        raise UserServiceException, "HTTP Error 500: {}".format(response.reason)
    return response

def get_digest_subscribers():
    """
    Generator function that calls the edX user API and yields a dict for each
    user opted in for digest notifications.

    The returned dicts will have keys "id", "name", and "email" (all strings).
    """
    api_url = settings.US_URL_BASE + '/user_api/v1/preferences/{key}/users/'.format(key=DIGEST_NOTIFICATION_PREFERENCE_KEY)
    params = {
        'page_size': settings.US_RESULT_PAGE_SIZE,
        'page': 1
    }
    
    logger.info('calling user api for digest subscribers')
    while True:
        with dog_stats_api.timer('notifier.get_digest_subscribers.time'):
            data = _http_get(api_url, params=params, headers=_headers(), **_auth()).json
        for result in data['results']:
            del result['url']  # not used
            yield result
        if data['next'] is None:
            break
        params['page'] += 1


def get_user(user_id):
    api_url = '{}/user_api/v1/users/{}/'.format(settings.US_URL_BASE, user_id)
    logger.info('calling user api for user %s', user_id)
    with dog_stats_api.timer('notifier.get_user.time'):
        r = _http_get(api_url, headers=_headers(), **_auth())
        if r.status_code == 200:
            user = r.json
            del user['url']
            return user
        elif r.status_code == 404:
            return None
        else:
            r.raise_for_status()
            raise Exception(
                'unhandled response from user service: %s %s' %
                (r.status_code, r.reason))


# implementation mirrors that in
# https://github.com/edx/edx-platform/blob/master/lms/djangoapps/notification_prefs/views.py
class UsernameCipher(object):
    """
    A transformation of a username to/from an opaque token

    The purpose of the token is to make one-click unsubscribe links that don't
    require the user to log in. To prevent users from unsubscribing other users,
    we must ensure the token cannot be computed by anyone who has this
    source code. The token must also be embeddable in a URL.

    Thus, we take the following steps to encode (and do the inverse to decode):
    1. Pad the UTF-8 encoding of the username with PKCS#7 padding to match the
       AES block length
    2. Generate a random AES block length initialization vector
    3. Use AES-256 (with a hash of settings.SECRET_KEY as the encryption key)
       in CBC mode to encrypt the username
    4. Prepend the IV to the encrypted value to allow for initialization of the
       decryption cipher
    5. base64url encode the result
    """

    @staticmethod
    def _get_aes_cipher(initialization_vector):
        hash_ = sha256()
        hash_.update(settings.SECRET_KEY)
        return AES.new(hash_.digest(), AES.MODE_CBC, initialization_vector)

    @staticmethod
    def _add_padding(input_str):
        """Return `input_str` with PKCS#7 padding added to match AES block length"""
        padding_len = AES.block_size - len(input_str) % AES.block_size
        return input_str + padding_len * chr(padding_len)

    @staticmethod
    def _remove_padding(input_str):
        """Return `input_str` with PKCS#7 padding trimmed to match AES block length"""
        num_pad_bytes = ord(input_str[-1])
        if num_pad_bytes < 1 or num_pad_bytes > AES.block_size or num_pad_bytes >= len(input_str):
            raise UsernameDecryptionException("padding")
        return input_str[:-num_pad_bytes]

    @staticmethod
    def encrypt(username):
        initialization_vector = Random.new().read(AES.block_size)
        aes_cipher = UsernameCipher._get_aes_cipher(initialization_vector)
        return urlsafe_b64encode(
            initialization_vector +
            aes_cipher.encrypt(UsernameCipher._add_padding(username.encode("utf-8")))
        )

    @staticmethod
    def decrypt(token):
        try:
            base64_decoded = urlsafe_b64decode(token)
        except TypeError:
            raise UsernameDecryptionException("base64url")

        if len(base64_decoded) < AES.block_size:
            raise UsernameDecryptionException("initialization_vector")

        initialization_vector = base64_decoded[:AES.block_size]
        aes_encrypted = base64_decoded[AES.block_size:]
        aes_cipher = UsernameCipher._get_aes_cipher(initialization_vector)

        try:
            decrypted = aes_cipher.decrypt(aes_encrypted)
        except ValueError:
            raise UsernameDecryptionException("aes")

        return UsernameCipher._remove_padding(decrypted)

