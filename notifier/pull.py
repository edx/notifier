"""
"""

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


def process_cs_response(payload, user_info_by_id):
    """
    Transforms and filters the comments service response to generate Digest
    objects for each user supplied in user_info_by_id.
    """
    for user_id, user_content in payload.iteritems():
        digest = _build_digest(user_content, user_info_by_id[user_id])
        if not digest.empty:
            yield user_id, digest

def _build_digest(user_content, user_info):
    """
    Transforms course/thread/item data from the comments service's response
    into a Digest for a single user.

    Results will only include threads/items from courses in which the user has
    been reported to be actively enrolled (by the user service).
    """
    return Digest(
        filter(
            lambda c: not c.empty,
            [
                _build_digest_course(
                    course_id,
                    course_dict,
                    user_info["course_info"][course_id]
                )
                for course_id, course_dict in user_content.iteritems()
                if course_id in user_info["course_info"]
            ]
        )
    )

def _build_digest_course(course_id, course_content, user_course_info):
    """
    Transforms thread/item data from the comments service's response for a
    specific user and course.

    The threads returned will be filtered by a group-level access check.
    """
    return DigestCourse(
        course_id,
        [
            _build_digest_thread(thread_id, course_id, thread_content)
            for thread_id, thread_content in course_content.iteritems()
            if (
                # the user is allowed to "see all cohorts" in the course, or
                user_course_info['see_all_cohorts'] or

                # the thread is not associated with a group, or
                thread_content.get('group_id') is None or

                # the user's cohort_id matches the thread's group_id
                user_course_info['cohort_id'] == thread_content.get('group_id')
            )
        ]
    )

def _build_digest_thread(thread_id, course_id, thread_content):
    """
    Parses a thread information for the given course and thread.
    """
    return DigestThread(
        thread_id,
        course_id,
        thread_content["commentable_id"],
        thread_content["title"],
        [_build_digest_item(item_dict) for item_dict in thread_content["content"]]
    )

def _build_digest_item(item_dict):
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
    user id and user is the user dict returned by edx notifier_api.
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
    user_ids_string = ','.join(map(str, sorted(users_by_id.keys())))
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
        logger.info('calling comments service to pull digests for %d user(s)', len(users_by_id))
        resp = _http_post(api_url, headers=headers, data=data)

    return process_cs_response(resp.json(), users_by_id)
