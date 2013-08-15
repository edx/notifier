"""
"""

from collections import namedtuple
import datetime
import logging
import sys

from dateutil.parser import parse as date_parse
from django.conf import settings
from dogapi import dog_stats_api
import requests

from notifier.digest import Digest, DigestCourse, DigestThread, DigestItem

logger = logging.getLogger(__name__)


class CommentsServiceException(Exception):
    pass

def _http_post(*a, **kw):
    try:
        logger.debug('POST %s %s', a[0], kw)
        response = requests.post(*a, **kw)
    except requests.exceptions.ConnectionError, e:
        _, msg, tb = sys.exc_info()
        raise CommentsServiceException, "comments service request failed: {}".format(msg), tb
    if response.status_code == 500:
        raise CommentsServiceException, "comments service HTTP Error 500: {}".format(response.reason)
    return response


class Parser(object):
    
    @staticmethod
    def parse(payload):
        return ((user_id, Parser.digest(user_id, user_dict)) 
                for user_id, user_dict in payload.iteritems())
    
    @staticmethod
    def digest(user_id, user_dict):
        return Digest(
                [Parser.course(course_id, course_dict)
                    for course_id, course_dict in user_dict.iteritems()]
                )

    @staticmethod
    def course(course_id, course_dict):
        return DigestCourse(
                course_id,
                [Parser.thread(thread_id, course_id, thread_content)
                    for thread_id, thread_content in course_dict.iteritems()]
                )

    @staticmethod
    def thread(thread_id, course_id, thread_dict):
        return DigestThread(
                thread_id,
                course_id,
                thread_dict["commentable_id"],
                thread_dict["title"],
                [Parser.item(item_dict)
                    for item_dict in thread_dict["content"]]
                )

    @staticmethod
    def item(item_dict):
        return DigestItem(
                item_dict["body"],
                item_dict["username"],
                date_parse(item_dict["updated_at"])
                )


def generate_digest_content(user_ids, from_dt, to_dt):
    """
    Function that calls the edX comments service API and yields a
    tuple of (user_id, digest) for each specified user that has >0
    discussion updates between the specified points in time.

    `user_ids` should be an iterable of edX user ids.
    `from_dt` and `to_dt` should be datetime.datetime objects representing
    the desired time window.

    In each yielded tuple, the `user_id` part will contain one of the values
    passed in `user_ids` and the `digest` part will contain a Digest object
    (see notifier.digest.Digest for structure details).

    The order in which user-digest results will be yielded is undefined, and
    if no updates are found for any user_id in the given time period, no
    user-digest tuple will be yielded for them (therefore, depending on the
    parameters passed, this function may not yield anything).
    """

    # set up and execute the API call
    api_url = settings.CS_URL_BASE + '/api/v1/notifications'
    user_ids = ','.join(map(str, user_ids))
    dt_format = '%Y-%m-%d %H:%M:%S%z'
    params = {
        'api_key': settings.CS_API_KEY,
        }
    data = {
        'user_ids': user_ids,
        'from': from_dt.strftime(dt_format),
        'to': to_dt.strftime(dt_format)
    }

    with dog_stats_api.timer('notifier.comments_service.time'):
        logger.info('calling comments service to pull digests for %d user(s)', len(user_ids))
        res = _http_post(api_url, params=params, data=data).json

    return Parser.parse(res)

