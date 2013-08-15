"""
General formatting and rendering helpers for digest notifications.
"""

import datetime
import logging

from django.conf import settings
from django.template.loader import get_template
from django.template import Context
from django.utils.html import strip_tags
from statsd import statsd

from notifier.user import UsernameCipher

# maximum number of threads to display per course
MAX_COURSE_THREADS = 30
# maximum number of items (posts) to display per thread
MAX_THREAD_ITEMS = 10
# maximum number of characters to allow in thread title, before truncating
THREAD_TITLE_MAXLEN = 140
# maximum number of characters to allow in thread post, before truncating
THREAD_ITEM_MAXLEN = 140


logger = logging.getLogger(__name__)


def _clean_markup(content):
    """
    Remove any unwanted markup from `content` prior to rendering in digest form.

    >>> # strip html inside a post
    >>> _clean_markup('Hello, <strong>World!</strong>')
    u'Hello, World!'

    >>> # unbalanced / malformed is OK
    >>> _clean_markup('Hello, <strong color="green"/>World!<script type="invalid>')
    u'Hello, World!'
    """
    return strip_tags(content)


def _trunc(s, length):
    """
    Formatting helper.

    Truncate the string `s` to no more than `length`, using ellipsis and
    without chopping words.

    >>> _trunc("one two three", 13)
    'one two three'
    >>> _trunc("one two three", 12)
    'one two...'
    """
    s = s.strip()
    if len(s) <= length:
        # nothing to do
        return s
    # truncate, taking an extra -3 off the orig string for the ellipsis itself
    return s[:length - 3].rsplit(' ', 1)[0].strip() + '...'


def _join_and(values):
    """
    Formatting helper.

    Join a list of strings, using the comma and "and" properly (assuming
    English).

    >>> _join_and([])
    ''
    >>> _join_and(['spam'])
    'spam'
    >>> _join_and(['spam', 'eggs'])
    'spam and eggs'
    >>> _join_and(['spam', 'eggs', 'beans'])
    'spam, eggs, and beans'
    >>> _join_and(['spam', 'eggs', 'beans', 'cheese'])
    'spam, eggs, beans, and cheese'
    """
    if len(values) == 0:
        return ''
    elif len(values) == 1:
        return values[0]
    elif len(values) == 2:
        return ' and '.join(values)
    else:
        values[-1] = 'and ' + values[-1]
        return ', '.join(values)


def _get_course_title(course_id):
    """
    Formatting helper.

    Transform an edX course id (e.g. "MITx/6.002x/2012_Fall") into a string
    suitable for use as a course title in digest notifications.

    >>> _get_course_title("MITx/6.002x/2012_Fall")
    '6.002x MITx'
    """
    return ' '.join(reversed(course_id.split('/')[:2]))


def _get_course_url(course_id):
    """
    Formatting helper.

    Generate a click-through url for a given edX course id.

    >>> _get_course_url("MITx/6.002x/2012_Fall").replace(
    ...        settings.LMS_URL_BASE, "URL_BASE")
    'URL_BASE/courses/MITx/6.002x/2012_Fall/'
    """
    return '{}/courses/{}/'.format(settings.LMS_URL_BASE, course_id)


def _get_thread_url(course_id, thread_id, commentable_id):
    """
    Formatting helper.

    Generate a click-through url for a specific discussion thread in an edX
    course.
    """
    thread_path = 'discussion/forum/{}/threads/{}'.format(commentable_id, thread_id)
    return _get_course_url(course_id) + thread_path


def _get_unsubscribe_url(username):
    """
    Formatting helper.

    Generate a click-through url to unsubscribe a user from digest notifications,
    using an encrypted token based on the username.
    """
    token = UsernameCipher.encrypt(username)
    return '{}/notification_prefs/unsubscribe/{}/'.format(settings.LMS_URL_BASE, token)


class Digest(object):
    def __init__(self, courses):
        self.courses = sorted(courses, key=lambda c: c.title.lower())

class DigestCourse(object):
    def __init__(self, course_id, threads):
        self.title = _get_course_title(course_id)
        self.url = _get_course_url(course_id)
        self.thread_count = len(threads) # not the same as len(self.threads), see below
        self.threads = sorted(threads, reverse=True, key=lambda t: t.dt)[:MAX_COURSE_THREADS]

class DigestThread(object):
    def __init__(self, thread_id, course_id, commentable_id, title, items):
        self.title = _trunc(_clean_markup(title), THREAD_TITLE_MAXLEN)
        self.url = _get_thread_url(course_id, thread_id, commentable_id)
        self.items = sorted(items, reverse=True, key=lambda i: i.dt)[:MAX_THREAD_ITEMS]
 
    @property
    def dt(self):
        return max(item.dt for item in self.items)

class DigestItem(object):
    def __init__(self, body, author, dt):
        self.body = _trunc(_clean_markup(body), THREAD_ITEM_MAXLEN)
        self.author = author
        self.dt = dt


@statsd.timed('notifier.digest_render.elapsed')
def render_digest(user, digest, title, description):
    """
    Generate HTML and plaintext renderings of digest material, suitable for
    emailing.


    `user` should be a dictionary with the following keys: "id", "name",
    "email" (all values should be nonempty strings).

    `digest` should be a Digest object as defined above in this module.

    `title` and `description` are brief strings to be displayed at the top
    of the email message.


    Returns two strings: (text_body, html_body).
    """
    logger.info("rendering email message: {user_id: %s}", user['id'])
    context = Context({
        'user': user,
        'digest': digest,
        'title': title,
        'description': description,
        'course_count': len(digest.courses),
        'course_names': _join_and([course.title for course in digest.courses]),
        'thread_count': sum(course.thread_count for course in digest.courses),
        'logo_image_url': "{}/static/images/header-logo.png".format(settings.LMS_URL_BASE),
        'unsubscribe_url': _get_unsubscribe_url(user['username'])
        })
    
    text = get_template('digest-email.txt').render(context)
    html = get_template('digest-email.html').render(context)

    return (text, html)
