"""
Celery tasks for generating and sending digest emails.
"""
from contextlib import closing
from datetime import datetime, timedelta
import logging
import requests

from boto.ses.exceptions import SESMaxSendingRateExceededError
import celery
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from notifier.connection_wrapper import get_connection
from notifier.digest import render_digest
from notifier.pull import generate_digest_content, CommentsServiceException
from notifier.user import get_digest_subscribers, UserServiceException

logger = logging.getLogger(__name__)


@celery.task(rate_limit=settings.FORUM_DIGEST_TASK_RATE_LIMIT, max_retries=settings.FORUM_DIGEST_TASK_MAX_RETRIES)
def generate_and_send_digests(users, from_dt, to_dt):
    """
    This task generates and sends forum digest emails to multiple users in a
    single background operation.

    `users` is an iterable of dictionaries, as returned by the edx user_api
    (required keys are "id", "name", "email", "preferences", and "course_info").

    `from_dt` and `to_dt` are datetime objects representing the start and end
    of the time window for which to generate a digest.
    """
    users_by_id = dict((str(u['id']), u) for u in users)
    msgs = []
    try:
        with closing(get_connection()) as cx:
            for user_id, digest in generate_digest_content(users_by_id, from_dt, to_dt):
                user = users_by_id[user_id]
                # format the digest
                text, html = render_digest(
                    user, digest, settings.FORUM_DIGEST_EMAIL_TITLE, settings.FORUM_DIGEST_EMAIL_DESCRIPTION)
                # send the message through our mailer
                msg = EmailMultiAlternatives(
                    settings.FORUM_DIGEST_EMAIL_SUBJECT,
                    text,
                    settings.FORUM_DIGEST_EMAIL_SENDER,
                    [user['email']]
                )
                msg.attach_alternative(html, "text/html")
                msgs.append(msg)
            if msgs:
                cx.send_messages(msgs)
            if settings.DEAD_MANS_SNITCH_URL:
                requests.post(settings.DEAD_MANS_SNITCH_URL)
    except (CommentsServiceException, SESMaxSendingRateExceededError) as e:
        # only retry if no messages were successfully sent yet.
        if not any((getattr(msg, 'extra_headers', {}).get('status') == 200 for msg in msgs)):
            raise generate_and_send_digests.retry(exc=e)
        else:
            # raise right away, since we don't support partial retry
            raise


def _time_slice(minutes, now=None):
    """
    Returns the most recently-elapsed time slice of the specified length (in
    minutes), as of the specified datetime (defaults to utcnow).
    
    `minutes` must be greater than one, less than or equal to 1440, and a factor 
    of 1440 (so that no time slice spans across multiple days). 
    
    >>> _time_slice(1, datetime(2013, 1, 1, 0, 0))
    (datetime.datetime(2012, 12, 31, 23, 59), datetime.datetime(2013, 1, 1, 0, 0))
    >>> _time_slice(1, datetime(2013, 1, 1, 0, 1))
    (datetime.datetime(2013, 1, 1, 0, 0), datetime.datetime(2013, 1, 1, 0, 1))
    >>> _time_slice(1, datetime(2013, 1, 1, 1, 1))
    (datetime.datetime(2013, 1, 1, 1, 0), datetime.datetime(2013, 1, 1, 1, 1))
    >>> _time_slice(15, datetime(2013, 1, 1, 0))
    (datetime.datetime(2012, 12, 31, 23, 45), datetime.datetime(2013, 1, 1, 0, 0))
    >>> _time_slice(15, datetime(2013, 1, 1, 0, 14))
    (datetime.datetime(2012, 12, 31, 23, 45), datetime.datetime(2013, 1, 1, 0, 0))
    >>> _time_slice(15, datetime(2013, 1, 1, 0, 14, 59))
    (datetime.datetime(2012, 12, 31, 23, 45), datetime.datetime(2013, 1, 1, 0, 0))
    >>> _time_slice(15, datetime(2013, 1, 1, 0, 15, 0))
    (datetime.datetime(2013, 1, 1, 0, 0), datetime.datetime(2013, 1, 1, 0, 15))
    >>> _time_slice(1440, datetime(2013, 1, 1))
    (datetime.datetime(2012, 12, 31, 0, 0), datetime.datetime(2013, 1, 1, 0, 0))
    >>> _time_slice(1440, datetime(2013, 1, 1, 23, 59))
    (datetime.datetime(2012, 12, 31, 0, 0), datetime.datetime(2013, 1, 1, 0, 0))
    >>> e = None
    >>> try:
    ...     _time_slice(14, datetime(2013, 1, 2, 0, 0))
    ... except AssertionError, e:
    ...     pass
    ... 
    >>> e is not None
    True
    """
    assert minutes > 0
    assert minutes <= 1440
    assert 1440 % minutes == 0
    now = now or datetime.utcnow()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) 
    minutes_since_midnight = (now - midnight).seconds / 60
    dt_end = midnight + timedelta(minutes=(minutes_since_midnight / minutes) * minutes)
    dt_start = dt_end - timedelta(minutes=minutes)
    return (dt_start, dt_end)

@celery.task(max_retries=settings.DAILY_TASK_MAX_RETRIES, default_retry_delay=settings.DAILY_TASK_RETRY_DELAY)
def do_forums_digests():
    
    def batch_digest_subscribers():
        batch = []
        for v in get_digest_subscribers():
            batch.append(v)
            if len(batch)==settings.FORUM_DIGEST_TASK_BATCH_SIZE:
                yield batch
                batch = []
        if batch:
            yield batch

    from_dt, to_dt = _time_slice(settings.FORUM_DIGEST_TASK_INTERVAL)

    logger.info("Beginning forums digest task: from_dt=%s to_dt=%s", from_dt, to_dt)
    try:
        for user_batch in batch_digest_subscribers():
            generate_and_send_digests.delay(user_batch, from_dt, to_dt)
    except UserServiceException, e:
        raise do_forums_digests.retry(exc=e)
