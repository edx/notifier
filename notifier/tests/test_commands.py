"""
"""
import datetime
import json
from os.path import dirname, join

from django.conf import settings
from django.core import management
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch, Mock

from notifier.management.commands import forums_digest
from notifier.tests.test_tasks import usern


class CommandsTestCase(TestCase):
    """
    Test notifier management commands
    """

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory',)
    def test_forums_digest(self):
        pass

    def test_forums_digest_flagged(self):
        """
        Test typical use of command
        """
        return_value = [usern(i) for i in xrange(10)]
        with patch('notifier.tasks.get_moderators', return_value=return_value) as m:
            input_file = "./notifier/tests/fixtures/flagged.list"
            management.call_command('forums_digest_flagged',
                courses_file=input_file,
            )

