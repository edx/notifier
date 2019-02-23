"""
"""
import datetime

import celery
from dateutil.parser import parse as date_parse
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
import json
import logging
from optparse import make_option
import pytz
import requests
import sys

from notifier.digest import render_digest, Digest, DigestCourse, DigestThread, DigestItem
from notifier.pull import generate_digest_content
from notifier.tasks import generate_and_send_digests
from notifier.user import get_digest_subscribers, get_user


logger = logging.getLogger(__name__)


class DigestJSONEncoder(DjangoJSONEncoder):

    def default(self, o):
        if isinstance(o, (Digest, DigestCourse, DigestThread, DigestItem)):
            return o.__dict__
        else:
            return super(DigestJSONEncoder, self).default(o)


class Command(BaseCommand):

    """
    """

    option_list = BaseCommand.option_list + (
        make_option('--to_datetime',
                    action='store',
                    dest='to_datetime',
                    default=None,
                    help='datetime as of which to generate digest content, in ISO-8601 format (UTC).  Defaults to today at 00:00 (UTC).'),
        make_option('--minutes',
                    action='store',
                    dest='minutes',
                    type='int',
                    default=1440,
                    help='number of minutes up to TO_DATETIME for which to generate digest content.  Defaults to 1440 (one day).'),
        make_option('--users',
                    action='store',
                    dest='users_str',
                    default=None,
                    help='send digests for the specified users only (regardless of opt-out settings!)'),
        make_option('--show-content',
                    action='store_true',
                    dest='show_content',
                    default=None,
                    help='output the retrieved content only (don\'t send anything)'),
        make_option('--show-users',
                    action='store_true',
                    dest='show_users',
                    default=None,
                    help='output the retrieved users only (don\'t fetch content or send anything)'),
        make_option('--show-text',
                    action='store_true',
                    dest='show_text',
                    default=None,
                    help='output the rendered text body of the first user-digest generated, and exit (don\'t send anything)'),
        make_option('--show-html',
                    action='store_true',
                    dest='show_html',
                    default=None,
                    help='output the rendered html body of the first user-digest generated, and exit (don\'t send anything)'),
    )

    def get_specific_users(self, user_ids):
        # this makes an individual HTTP request for each user -
        # it is only intended for use with small numbers of users
        # (e.g. for diagnostic purposes).
        users = []
        for user_id in user_ids:
            user = get_user(user_id)
            if user:
                users.append(user)
        return users

    def show_users(self, users):
        json.dump(list(users), self.stdout)

    def show_content(self, users, from_dt, to_dt):
        users_by_id = dict((str(u['id']), u) for u in users)
        all_content = generate_digest_content(users_by_id, from_dt, to_dt)
        # use django's encoder; builtin one doesn't handle datetime objects
        json.dump(list(all_content), self.stdout, cls=DigestJSONEncoder)

    def show_rendered(self, fmt, users, from_dt, to_dt):
        users_by_id = dict((str(u['id']), u) for u in users)

        def _fail(msg):
            logger.warning('could not show rendered %s: %s', fmt, msg)

        try:
            user_id, digest = next(generate_digest_content(users_by_id, from_dt, to_dt))
        except StopIteration:
            _fail('no digests found')
            return

        text, html = render_digest(
            users_by_id[user_id],
            digest,
            settings.FORUM_DIGEST_EMAIL_TITLE,
            settings.FORUM_DIGEST_EMAIL_DESCRIPTION
        )
        if fmt == 'text':
            print >> self.stdout, text
        elif fmt == 'html':
            print >> self.stdout, html

    def handle(self, *args, **options):
        """
        """

        # get user data
        if options.get('users_str') is not None:
            # explicitly-specified users
            user_ids = [v.strip() for v in options['users_str'].split(',')]
            users = self.get_specific_users(user_ids)
        else:
            # get all the users subscribed to notifications
            users = get_digest_subscribers()  # generator

        if options.get('show_users'):
            self.show_users(users)
            return

        # determine time window
        if options.get('to_datetime'):
            to_datetime = date_parse(options['to_datetime'])
        else:
            to_datetime = datetime.datetime.utcnow().replace(
                hour=0, minute=0, second=0)
        from_datetime = to_datetime - \
            datetime.timedelta(minutes=options['minutes'])

        if options.get('show_content'):
            self.show_content(users, from_datetime, to_datetime)
            return

        if options.get('show_text'):
            self.show_rendered('text', users, from_datetime, to_datetime)
            return

        if options.get('show_html'):
            self.show_rendered('html', users, from_datetime, to_datetime)
            return

        # invoke `tasks.generate_and_send_digests` via celery, in groups of
        # 10
        def queue_digests(some_users):
            generate_and_send_digests.delay(
                some_users,
                from_datetime,
                to_datetime,
                language=settings.LANGUAGE_CODE
            )

        user_batch = []
        for user in users:
            user_batch.append(user)
            if len(user_batch) == settings.FORUM_DIGEST_TASK_BATCH_SIZE:
                queue_digests(user_batch)
                user_batch = []
        # get the remainder if any
        if user_batch:
            queue_digests(user_batch)
