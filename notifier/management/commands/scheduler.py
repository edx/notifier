from apscheduler.scheduler import Scheduler
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notifier.tasks import do_forums_digests

# N.B. standalone=True means that sched.start() will block until forcibly stopped.
sched = Scheduler(standalone=True)

@sched.cron_schedule(**settings.DIGEST_CRON_SCHEDULE)
def digest_job():
    do_forums_digests.delay()

class Command(BaseCommand):

    help = """Start the notifier scheduler.  Important environment settings are:
    
    BROKER_URL
        Celery broker URL.  Point this where your celery workers look for tasks.
    
    FORUM_DIGEST_TASK_INTERVAL (optional)
        Number of minutes between digests (int).  Default is 1440.  The value must
        be a factor of 1440.  If 1440, the forums digest job will fire at midnight
        daily.

    """

    def handle(self, *args, **options):
        sched.start()
