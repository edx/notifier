from apscheduler.scheduler import Scheduler
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notifier.tasks import do_forums_digests
from notifier.tasks import do_forums_digests_flagged

# N.B. standalone=True means that sched.start() will block until forcibly stopped.
sched = Scheduler(standalone=True)

@sched.cron_schedule(**settings.DIGEST_CRON_SCHEDULE)
def digest_job():
    do_forums_digests.delay()

def digest_job_flagged():
    """
    Schedule this task via cron job
    """
    do_forums_digests_flagged()

class Command(BaseCommand):

    help = """Start the notifier scheduler.  Important environment settings are:

    BROKER_URL
        Celery broker URL.  Point this where your celery workers look for tasks.

    FORUM_DIGEST_TASK_INTERVAL (optional)
        Number of minutes between digests (int).  Default is 1440.  The value must
        be a factor of 1440.  If 1440, the forums digest job will fire at midnight
        daily.

    FORUM_DIGEST_TASK_INTERVAL_FLAGGED (optional)
        Number of minutes between digests (int).  Default is 0, which disables
        it.  The value must be a factor of 1440.  If 1440, the forums digest
        job will fire at midnight daily.
    """

    def handle(self, *args, **options):
        if settings.FLAGGED_FORUM_DIGEST_TASK_INTERVAL > 0:
            sched.add_cron_job(digest_job_flagged, **settings.DIGEST_CRON_SCHEDULE_FLAGGED)
        sched.start()
