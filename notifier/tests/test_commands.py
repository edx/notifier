"""
"""
import datetime
import json
from os.path import dirname, join

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch, Mock

from notifier.management.commands import forums_digest

class CommandsTestCase(TestCase):

    """
    """

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory',)
    def test_forums_digest(self):
        pass
