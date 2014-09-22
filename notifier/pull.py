"""
"""

import itertools
import logging
import sys

from dateutil.parser import parse as date_parse
from django.conf import settings
from dogapi import dog_stats_api
import requests

from notifier.digest import Digest, DigestCourse, DigestThread, DigestItem

logger = logging.getLogger(__name__)


class CommentsServiceException(Exception):
    """
    Base class for exceptions raised by the Comments Service.
    """
    pass


def _http_post(*a, **kw):
    """
    Helper for posting HTTP requests to the comments service.
    """
    try:
        logger.debug('POST %s %s', a[0], kw)
        response = requests.post(*a, **kw)
    except requests.exceptions.ConnectionError, e:
        _, msg, tb = sys.exc_info()
        raise CommentsServiceException, "comments service request failed: {}".format(msg), tb
    if response.status_code != 200:
        raise CommentsServiceException, "comments service HTTP Error {code}: {reason}".format(code=response.status_code, reason=response.reason)
    return response


def user_has_access_to_thread(user, course_id, group_id):
    """
    Returns whether the given user has access to the given thread.
    """

    # get the user's course information
    user_course_info = user.setdefault('course_info', {}).setdefault(course_id, {})

    return (
        # the user is enrolled in the course
        user_course_info and (

            # the thread is not associated with a group, or
            (group_id is None) or

            # the user is allowed to "see all cohorts" in the course, or
            (user_course_info.get('see_all_cohorts', False)) or

            # the user's cohort_id matches the thread's group_id
            (user_course_info.get('cohort_id', None) == group_id)
        )
    )


class Parser(object):
    """
    Provides methods to parse the payload returned by the comments service.
    """
    @staticmethod
    def parse(payload, user_info_by_id):
        """
        Parses the given payload using the users' course and cohort information in the given user_info_by_id.
        """
        return (
            (user_id, Parser.digest(user_digest, user_info_by_id.setdefault(user_id, {})))
            for user_id, user_digest in payload.iteritems()
        )
    
    @staticmethod
    def digest(user_digest_dict, user_info):
        """
        Parses a user's digest using that user's course and cohort information.
        """
        return Digest(
            [
                Parser.course(course_id, course_dict, user_info)
                for course_id, course_dict in user_digest_dict.iteritems()
            ]
        )

    @staticmethod
    def course(course_id, course_dict, user_info):
        """
        Parses a user's digest for the given course using that user's course and cohort information.
        """
        return DigestCourse(
            course_id,
            [
                Parser.thread(thread_id, course_id, thread_content)
                for thread_id, thread_content in course_dict.iteritems()
                if user_has_access_to_thread(user_info, course_id, thread_content.get("group_id", None))
            ]
        )

    @staticmethod
    def thread(thread_id, course_id, thread_dict):
        """
        Parses a thread information for the given course and thread.
        """
        return DigestThread(
            thread_id,
            course_id,
            thread_dict["commentable_id"],
            thread_dict["title"],
            [Parser.item(item_dict) for item_dict in thread_dict["content"]]
        )

    @staticmethod
    def item(item_dict):
        """
        Parses a digest item.
        """
        return DigestItem(
            item_dict["body"],
            item_dict["username"],
            date_parse(item_dict["updated_at"])
        )


def generate_digest_content(users_by_id, from_dt, to_dt):
    """
    Function that calls the edX comments service API and yields a
    tuple of (user_id, digest) for each specified user that has >0
    discussion updates between the specified points in time.

    `users_by_id` should be a dict of {user_id: user} where user-id is an edX
    user id and user is the user dict returned by edx user_api.
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
    user_ids_string = ','.join(map(str, sorted(users_by_id)))
    dt_format = '%Y-%m-%d %H:%M:%S%z'
    headers = {
        'X-Edx-Api-Key': settings.CS_API_KEY,
    }
    data = {
        'user_ids': user_ids_string,
        'from': from_dt.strftime(dt_format),
        'to': to_dt.strftime(dt_format)
    }

    with dog_stats_api.timer('notifier.comments_service.time'):
        logger.info('calling comments service to pull digests for %d user(s)', len(user_ids_string))
        resp = _http_post(api_url, headers=headers, data=data)

    return Parser.parse(resp.json(), users_by_id)
