"""
Database models for notifier.
"""
from datetime import datetime, timedelta

from django.db import models


class ForumDigestTask(models.Model):
    """
    ForumDigestTask model is used for synchronization between notifier schedulers to avoid multiple
    scheduler instances from scheduling duplicate forum digest tasks.
    """
    from_dt = models.DateTimeField(help_text="Beginning of time slice for which to send forum digests.")
    to_dt = models.DateTimeField(help_text="End of time slice for which to send forum digests.")
    node = models.CharField(max_length=255, blank=True, help_text="Name of node that scheduled the task.")
    created = models.DateTimeField(auto_now_add=True, help_text="Time at which the task was scheduled.")

    class Meta:
        unique_together = (('from_dt', 'to_dt'),)

    @classmethod
    def prune_old_tasks(cls, day_limit):
        """
        Deletes all tasks older than `day_limit` days from the database.
        """
        last_keep_dt = datetime.utcnow() - timedelta(days=day_limit)
        cls.objects.filter(created__lt=last_keep_dt).delete()
