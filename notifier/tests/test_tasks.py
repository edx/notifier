"""
"""
from contextlib import nested
import datetime
import json
from os.path import dirname, join
import platform

from boto.ses.exceptions import SESMaxSendingRateExceededError
from django.conf import settings
from django.core import mail as djmail
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch, Mock

from notifier.models import ForumDigestTask
from notifier.tasks import generate_and_send_digests, do_forums_digests
from notifier.pull import process_cs_response, CommentsServiceException
from notifier.user import UserServiceException, DIGEST_NOTIFICATION_PREFERENCE_KEY
from .utils import make_user_info


# fixture data helper
usern = lambda n: {
    'name': 'user%d' % n,
    'id': n,
    'email': 'user%d@dummy.edu' %n,
    'preferences': {
        DIGEST_NOTIFICATION_PREFERENCE_KEY: 'pref%d' % n,
    },
    'course_info': {

    }
}


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   BROKER_BACKEND='memory',)
class TasksTestCase(TestCase):

    """
    """

    def _check_message(self, user, digest, message):
        actual_text = message.body
        actual_html, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, 'text/html')

        self.assertEqual(message.from_email, settings.FORUM_DIGEST_EMAIL_SENDER)
        self.assertEqual(message.to, [user['email']])
        self.assertEqual(message.subject, settings.FORUM_DIGEST_EMAIL_SUBJECT)

        self.assertTrue(user['name'] in actual_text)
        self.assertTrue(settings.FORUM_DIGEST_EMAIL_TITLE in actual_text)
        self.assertTrue(settings.FORUM_DIGEST_EMAIL_DESCRIPTION in actual_text)

        self.assertTrue(user['name'] in actual_html)
        self.assertTrue(settings.FORUM_DIGEST_EMAIL_TITLE in actual_html)
        self.assertTrue(settings.FORUM_DIGEST_EMAIL_DESCRIPTION in actual_html)

        for course in digest.courses:
            self.assertTrue(course.title in actual_text)
            self.assertTrue(course.title in actual_html)
            for thread in course.threads:
                self.assertTrue(thread.title in actual_text)
                self.assertTrue(thread.title in actual_html)
                for item in thread.items:
                    self.assertTrue(item.body in actual_text)
                    self.assertTrue(item.body in actual_html)

    def _process_cs_response_with_user_info(self, data):
        mock_user_info = make_user_info(data)
        return process_cs_response(data, mock_user_info)

    def test_generate_and_send_digests(self):
        """
        """
        data = json.load(
            open(join(dirname(__file__), 'cs_notifications.result.json')))

        user_id, digest = next(self._process_cs_response_with_user_info(data))
        user = usern(10)
        with patch('notifier.tasks.generate_digest_content', return_value=[(user_id, digest)]) as p:

            # execute task
            task_result = generate_and_send_digests.delay(
                [user],
                datetime.datetime.now(),
                datetime.datetime.now())
            self.assertTrue(task_result.successful())

            # message was sent
            self.assertTrue(hasattr(djmail, 'outbox'))
            self.assertEqual(1, len(djmail.outbox))

            # message has expected to, from, subj, and content
            self._check_message(user, digest, djmail.outbox[0])

    @override_settings(EMAIL_REWRITE_RECIPIENT='rewritten-address@domain.org')
    def test_generate_and_send_digests_rewrite_recipient(self):
        """
        """
        data = json.load(
            open(join(dirname(__file__), 'cs_notifications.result.json')))

        with patch(
            'notifier.tasks.generate_digest_content',
            return_value=self._process_cs_response_with_user_info(data)
        ):
            # execute task
            task_result = generate_and_send_digests.delay(
                (usern(n) for n in range(2, 11)), datetime.datetime.now(), datetime.datetime.now())
            self.assertTrue(task_result.successful())

            # all messages were sent
            self.assertTrue(hasattr(djmail, 'outbox'))
            self.assertEqual(9, len(djmail.outbox))

            # all messages' email addresses were rewritten
            for message in djmail.outbox:
                self.assertEqual(message.to, ['rewritten-address@domain.org'])

    def test_generate_and_send_digests_retry_ses(self):
        """
        """
        data = json.load(
            open(join(dirname(__file__), 'cs_notifications.result.json')))

        with patch(
            'notifier.tasks.generate_digest_content',
            return_value=list(self._process_cs_response_with_user_info(data))
        ):
            # setting this here because override_settings doesn't seem to
            # work on celery task configuration decorators
            expected_num_tries = 1 + settings.FORUM_DIGEST_TASK_MAX_RETRIES
            mock_backend = Mock(name='mock_backend', send_messages=Mock(
                side_effect=SESMaxSendingRateExceededError(400, 'Throttling')))
            with patch('notifier.connection_wrapper.dj_get_connection', return_value=mock_backend) as p2:
                # execute task - should fail, retry twice and still fail, then
                # give up
                try:
                    generate_and_send_digests.delay(
                        [usern(n) for n in range(2, 11)], datetime.datetime.now(), datetime.datetime.now())
                except SESMaxSendingRateExceededError as e:
                    self.assertEqual(
                        mock_backend.send_messages.call_count,
                        expected_num_tries)
                else:
                    # should have raised
                    self.fail('task did not retry twice before giving up')

    def test_generate_and_send_digests_retry_cs(self):
        """
        """
        with patch(
            'notifier.tasks.generate_digest_content',
            side_effect=CommentsServiceException('timed out')
        ) as mock_cs_call:
            # setting this here because override_settings doesn't seem to
            # work on celery task configuration decorators
            expected_num_tries = 1 + settings.FORUM_DIGEST_TASK_MAX_RETRIES
            try:
                generate_and_send_digests.delay(
                    [usern(n) for n in range(2, 11)], datetime.datetime.now(), datetime.datetime.now())
            except CommentsServiceException as e:
                self.assertEqual(mock_cs_call.call_count, expected_num_tries)
            else:
                # should have raised
                self.fail('task did not retry twice before giving up')

    @override_settings(FORUM_DIGEST_TASK_BATCH_SIZE=10)
    def test_do_forums_digests(self):
        # patch _time_slice
        # patch get_digest_subscribers
        dt1 = datetime.datetime.utcnow()
        dt2 = dt1 + datetime.timedelta(days=1)
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(11))),
            patch('notifier.tasks.generate_and_send_digests'),
            patch('notifier.tasks._time_slice', return_value=(dt1, dt2))
        ) as (p, t, ts):
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            self.assertEqual(t.delay.call_count, 2)
            t.delay.assert_called_with([usern(10)], dt1, dt2, language=settings.LANGUAGE_CODE)


    @override_settings(FORUM_DIGEST_TASK_BATCH_SIZE=10)
    def test_do_forums_digests_user_api_unavailable(self):
        # patch _time_slice
        # patch get_digest_subscribers
        dt1 = datetime.datetime.utcnow()
        dt2 = dt1 + datetime.timedelta(days=1)
        with nested(
            patch('notifier.tasks.get_digest_subscribers', side_effect=UserServiceException("could not connect!")),
            patch('notifier.tasks.generate_and_send_digests'),
        ) as (p, t):
            try:
                task_result = do_forums_digests.delay()
            except UserServiceException as e:
                self.assertEqual(p.call_count, settings.DAILY_TASK_MAX_RETRIES + 1)
                self.assertEqual(t.call_count, 0)
            else:
                # should have raised
                self.fail("task did not give up after exactly 3 attempts")


    @override_settings(FORUM_DIGEST_TASK_BATCH_SIZE=10)
    def test_do_forums_digests_creates_database_entry(self):
        # patch _time_slice
        # patch get_digest_subscribers
        dt1 = datetime.datetime.utcnow()
        dt2 = dt1 + datetime.timedelta(days=1)
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(11))),
            patch('notifier.tasks.generate_and_send_digests'),
            patch('notifier.tasks._time_slice', return_value=(dt1, dt2))
        ) as (p, t, ts):
            self.assertEqual(ForumDigestTask.objects.count(), 0)
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            self.assertEqual(ForumDigestTask.objects.count(), 1)
            model = ForumDigestTask.objects.all()[0]
            self.assertEqual(model.from_dt, dt1)
            self.assertEqual(model.to_dt, dt2)
            self.assertEqual(model.node, platform.node())


    @override_settings(FORUM_DIGEST_TASK_BATCH_SIZE=10)
    def test_do_forums_digests_already_scheduled(self):
        # patch _time_slice
        # patch get_digest_subscribers
        dt1 = datetime.datetime.utcnow()
        dt2 = dt1 + datetime.timedelta(days=1)
        dt3 = dt2 + datetime.timedelta(days=1)
        # Scheduling the task for the first time sends the digests:
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(10))),
            patch('notifier.tasks._time_slice', return_value=(dt1, dt2)),
            patch('notifier.tasks.generate_and_send_digests')
        ) as (_gs, _ts, t):
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            self.assertEqual(t.delay.call_count, 1)
        # Scheduling the task with the same time slice again does nothing:
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(10))),
            patch('notifier.tasks._time_slice', return_value=(dt1, dt2)),
            patch('notifier.tasks.generate_and_send_digests')
        ) as (_gs, _ts, t):
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            self.assertEqual(t.delay.call_count, 0)
        # Scheduling the task with a different time slice sends the digests:
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(10))),
            patch('notifier.tasks._time_slice', return_value=(dt2, dt3)),
            patch('notifier.tasks.generate_and_send_digests')
        ) as (_gs, _ts, t):
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            self.assertEqual(t.delay.call_count, 1)


    @override_settings(FORUM_DIGEST_TASK_GC_DAYS=5)
    def test_do_forums_digests_creates_database_entry(self):
        # Create some ForumDigestTask objects.
        now = datetime.datetime.utcnow()
        # Populate the database with four ForumDigestTask objects (1, 2, 7, and 10 days old).
        for days in [1, 2, 7, 10]:
            dt = now - datetime.timedelta(days=days)
            from_dt = dt - datetime.timedelta(days=1)
            task = ForumDigestTask.objects.create(from_dt=from_dt, to_dt=dt, node='some-node')
            # Bypass field's auto_now_add by forcing the update via query manager.
            ForumDigestTask.objects.filter(pk=task.pk).update(created=dt)
        with nested(
            patch('notifier.tasks.get_digest_subscribers', return_value=(usern(n) for n in range(11))),
            patch('notifier.tasks.generate_and_send_digests'),
        ) as (p, t):
            # Two of the tasks that we created above are older than 5 days.
            five_days_ago = now - datetime.timedelta(days=5)
            self.assertEqual(ForumDigestTask.objects.filter(created__lt=five_days_ago).count(), 2)
            task_result = do_forums_digests.delay()
            self.assertTrue(task_result.successful())
            # The two tasks that are older than 5 days should be removed.
            self.assertEqual(ForumDigestTask.objects.filter(created__lt=five_days_ago).count(), 0)
