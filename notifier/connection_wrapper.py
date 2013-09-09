import logging
import time

from django.conf import settings
from django.core.mail import get_connection as dj_get_connection
from dogapi import dog_stats_api

logger = logging.getLogger(__name__)


class BackendWrapper(object):

    """A wrapper around Django's Email Backend, providing hooks
    for instrumentation and testing.
    """

    def __init__(self, backend):
        self._backend = backend
        logger.info("initialized connection wrapper with email backend: %s", backend)

    def send_messages(self, email_messages):

        # check settings hook for rewriting email recipient, act accordingly
        if settings.EMAIL_REWRITE_RECIPIENT:
            for message in email_messages:
                message.to = [settings.EMAIL_REWRITE_RECIPIENT]

        # send the messages
        t = time.time()
        msg_count = self._backend.send_messages(email_messages)
        elapsed = time.time() - t
        if msg_count > 0:
            logger.info('sent %s messages, elapsed: %.3fs' % (msg_count, elapsed))
            # report an average timing to datadog
            dog_stats_api.histogram('notifier.send.time', elapsed / msg_count)
            dog_stats_api.increment('notifier.send.count', msg_count)
            for msg in email_messages:
                hdrs = dict((k, v) for k, v in dict(msg.message()).iteritems()
                            if k.lower() not in ('date', 'from', 'subject', 'content-type', 'mime-version'))
                logger.info("sent email: {}".format(repr(hdrs)))
        if msg_count != len(email_messages):
            logger.warn('send_messages() was called with %s messages but return value was %s',
                len(email_messages), msg_count)
        return msg_count

    def close(self):
        # never raise Exceptions on close().
        try:
            self._backend.close()
        except Exception, e:
            logger.debug("self._backend.close() failed: %s", e)

    def __getattr__(self, a):
        return getattr(self._backend, a)


def get_connection(*a, **kw):
    return BackendWrapper(dj_get_connection(*a, **kw))
