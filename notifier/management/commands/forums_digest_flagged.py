from django.core.management.base import BaseCommand
import logging
from optparse import make_option

from notifier.tasks import do_forums_digests_flagged


logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    This Command is used to send a digest of flagged posts to forum moderators.
    """

    help = "Send a digest list of flagged forum posts to each moderator"
    option_list = BaseCommand.option_list + (
        make_option('--courses-file',
                    action='store',
                    dest='courses_file',
                    default=None,
                    help='send digests for the specified courses only' +
                        ' (defaults to fetching course list via Heroku)'),
    )

    def handle(self, *args, **options):
        """
        Handle a request to send a digest of flagged posts to forum moderators.
        """
        input_file = options.get('courses_file')
        do_forums_digests_flagged(input_file)

