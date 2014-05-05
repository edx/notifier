"""
Celery tasks for generating and sending digest emails.
"""
from contextlib import closing
from datetime import datetime, timedelta
import logging
import re
import subprocess

from boto.ses.exceptions import SESMaxSendingRateExceededError
import celery
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from notifier.connection_wrapper import get_connection
from notifier.digest import render_digest
from notifier.digest import render_digest_flagged
from notifier.pull import generate_digest_content
from notifier.user import get_digest_subscribers, UserServiceException
from notifier.user import get_moderators

logger = logging.getLogger(__name__)


@celery.task(rate_limit=settings.FORUM_DIGEST_TASK_RATE_LIMIT, max_retries=settings.FORUM_DIGEST_TASK_MAX_RETRIES)
def generate_and_send_digests(users, from_dt, to_dt):
    """
    This task generates and sends forum digest emails to multiple users in a
    single background operation.

    `users` is an iterable of dictionaries, as returned by the edx user_api
    (required keys are "id", "name", "username", and "email").

    `from_dt` and `to_dt` are datetime objects representing the start and end
    of the time window for which to generate a digest.
    """
    users_by_id = dict((str(u['id']), u) for u in users)
    with closing(get_connection()) as cx:
        msgs = []
        for user_id, digest in generate_digest_content(users_by_id.keys(), from_dt, to_dt):
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
        if not msgs:
            return
        try:
            cx.send_messages(msgs)
        except SESMaxSendingRateExceededError as e:
            # we've tripped the per-second send rate limit.  we generally
            # rely  on the django_ses auto throttle to prevent this,
            # but in case we creep over, we can re-queue and re-try this task
            # - if and only if none of the messages in our batch were
            # sent yet.
            # this implementation is also non-ideal in that the data will be
            # fetched from the comments service again in the event of a retry.
            if not any((getattr(msg, 'extra_headers', {}).get('status') == 200 for msg in msgs)):
                raise generate_and_send_digests.retry(exc=e)
            else:
                # raise right away, since we don't support partial retry
                raise

@celery.task(rate_limit=settings.FORUM_DIGEST_TASK_RATE_LIMIT, max_retries=settings.FORUM_DIGEST_TASK_MAX_RETRIES)
def generate_and_send_digests_flagged(messages):
    """
    This task generates and sends flagged forum digest emails to multiple users
    in a single background operation.

    Args:
        messages (gen): contains dicts with the following keys:
            course_id (str): identifier of the course
            recipient (dict): a single user dict
            posts (list): a list of post URLs
    """
    with closing(get_connection()) as cx:
        msgs = []
        for message in messages:
            text, html = render_digest_flagged(message)
            msg = EmailMultiAlternatives(
                settings.FORUM_DIGEST_EMAIL_SUBJECT,
                text,
                settings.FORUM_DIGEST_EMAIL_SENDER,
                [message['recipient']['email']],
            )
            msg.attach_alternative(html, "text/html")
            msgs.append(msg)
        if not msgs:
            return
        try:
            cx.send_messages(msgs)
        except SESMaxSendingRateExceededError as e:
            # we've tripped the per-second send rate limit.  we generally
            # rely  on the django_ses auto throttle to prevent this,
            # but in case we creep over, we can re-queue and re-try this task
            # - if and only if none of the messages in our batch were
            # sent yet.
            # this implementation is also non-ideal in that the data will be
            # fetched from the comments service again in the event of a retry.
            if not any((getattr(msg, 'extra_headers', {}).get('status') == 200 for msg in msgs)):
                raise generate_and_send_digests_flagged.retry(exc=e)
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
def do_forums_digests_flagged(input_file=None):
    """
    Generate and batch send digest emails for each thread specified in the input_file
    """
    def get_input(input_file):
        """
        Yield lines of input text to be processed

        Args:
            input_file (str): text file containing URLs of flagged thread posts

        Returns:
            gen: string lines of text
        """
        if input_file is not None:
            generator = get_input_file(input_file)
        else:
            generator = get_input_command()
        return generator

    def get_input_command():
        """
        Get input text from an executed command, e.g.
            heroku run rake flags:flagged --app=APP_NAME_HERE
        or
            bundle exec rake flags:flagged 2>/dev/null
        """
        command = settings.COMMAND_FETCH_FLAGGED_FORUM_POSTS.split(' ')
        return_value = subprocess.check_output(command)
        for line in return_value.split('\n'):
            yield line

    def get_input_file(input_file):
        """
        Yield each line of text from the input file.

        Args:
            input_file (str): text file containing URLs of flagged thread posts

        Returns:
            gen: string lines of text
        """
        with open(input_file, 'r') as fin:
            for i in fin:
                yield i.strip()

    def get_posts(input_file):
        """
        Parse posts and moderators from the corresponding text file

        Args:
            input_file (str): text file containing URLs of flagged thread posts

        Returns:
            dict: key=course_id, value={
                posts (list): strings of post URLs
                moderators (gen): users listed as moderators for specified course
                course_id (str): course identifier
            }
        """
        output = {}
        for line in get_input(input_file):
            match = re.search('^https?:\/\/\S+\/courses\/((?:[^\/]+\/){3})(\S*)', line)
            if match:
                course_id = match.group(1)
                course_id = course_id.strip()
                course_id = course_id[0:-1]
                thread_id = match.group(2)
                url = '{0}/courses/{1}/{2}'.format(settings.LMS_URL_BASE, course_id, thread_id)
                if not output.has_key(course_id):
                    output[course_id] = {}
                    output[course_id]['posts'] = list()
                    output[course_id]['moderators'] = get_moderators(course_id)
                    output[course_id]['course_id'] = course_id
                output[course_id]['posts'].append(url)
        return output

    def get_messages(input_file):
        """
        Yield message dicts to be used for sending digest emails to moderators

        Args:
            input_file (str): text file containing URLs of flagged thread posts

        Returns:
            dict gen:
                course_id (str): course identifier
                posts (list): strings of post URLs
                recipient (dict): a single user
        """
        posts = get_posts(input_file)
        for course_id in posts:
            for user in posts[course_id]['moderators']:
                yield {
                    'course_id': course_id,
                    'posts': posts[course_id]['posts'],
                    'recipient': user,
                }

    def batch(messages):
        """
        Generate and send messages in batches

        Args:
            messages (gen): contains dicts with the following keys:
                course_id (str): course identifier
                posts (list): strings of post URLs
                recipient (dict): a single user
        """
        batch = []
        for message in messages:
            batch.append(message)
            if len(batch) == settings.FORUM_DIGEST_TASK_BATCH_SIZE:
                generate_and_send_digests_flagged.delay(batch)
                batch = []
        # get the remainder if any
        if batch:
            generate_and_send_digests_flagged.delay(batch)

    messages = get_messages(input_file)
    batch(messages)


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
