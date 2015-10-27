from datetime import timedelta
import logging
import os
import platform

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME':  os.path.join(os.getenv('NOTIFIER_DB_DIR', '.'), 'notifier.db'),
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

INSTALLED_APPS = (
    'kombu.transport.django',
    'django_ses',
    'djcelery',
    'notifier',
)

SERVICE_NAME = 'notifier'

# Misc. Notifier Formatting

FORUM_DIGEST_EMAIL_SENDER = os.getenv('FORUM_DIGEST_EMAIL_SENDER', 'notifications@example.org')
FORUM_DIGEST_EMAIL_SUBJECT = os.getenv('FORUM_DIGEST_EMAIL_SUBJECT', 'Daily Discussion Digest')
FORUM_DIGEST_EMAIL_TITLE = os.getenv('FORUM_DIGEST_EMAIL_TITLE', 'Discussion Digest')
FORUM_DIGEST_EMAIL_DESCRIPTION = os.getenv(
    'FORUM_DIGEST_EMAIL_DESCRIPTION',
    'A digest of unread content from course discussions you are following.'
)
EMAIL_SENDER_POSTAL_ADDRESS = os.getenv('EMAIL_SENDER_POSTAL_ADDRESS')

# Environment-specific settings

# Application Environment
NOTIFIER_ENV = os.getenv('NOTIFIER_ENV', 'Development')

# email backend  settings
EMAIL_BACKEND = {
        'console': 'django.core.mail.backends.console.EmailBackend',
        'ses': 'django_ses.SESBackend',
        'smtp': 'django.core.mail.backends.smtp.EmailBackend'
        }[os.getenv('EMAIL_BACKEND', 'console')]
# The ideal setting for this is 1 / number_of_celery_workers * headroom, 
# where headroom is a multiplier to underrun the send rate limit (e.g.
# 0.9 to keep 10% behind the per-second rate limit at any given moment).
AWS_SES_AUTO_THROTTLE = 0.9

EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = os.getenv('EMAIL_PORT', 1025)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS')

# email settings independent of backend
EMAIL_REWRITE_RECIPIENT = os.getenv('EMAIL_REWRITE_RECIPIENT')

# LMS links, images, etc
LMS_URL_BASE = os.getenv('LMS_URL_BASE', 'http://localhost:8000')

# Comments Service Endpoint, for digest pulls
CS_URL_BASE = os.getenv('CS_URL_BASE', 'http://localhost:4567')
CS_API_KEY = os.getenv('CS_API_KEY', 'PUT_YOUR_API_KEY_HERE')

# User Service Endpoint, provides subscriber lists and notification-related user data
US_URL_BASE = os.getenv('US_URL_BASE', 'http://localhost:8000')
US_API_KEY = os.getenv('US_API_KEY', 'PUT_YOUR_API_KEY_HERE')
US_HTTP_AUTH_USER = os.getenv('US_HTTP_AUTH_USER', '')
US_HTTP_AUTH_PASS = os.getenv('US_HTTP_AUTH_PASS', '')
US_RESULT_PAGE_SIZE = 10

# Logging
LOG_FILE = os.getenv('LOG_FILE')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# datadog
DATADOG_API_KEY = os.getenv('DATADOG_API_KEY')

# celery
import djcelery
djcelery.setup_loader()
BROKER_URL = os.getenv('BROKER_URL', 'django://')

# limit the frequency at which the forum digest celery task may be run.
FORUM_DIGEST_TASK_RATE_LIMIT = os.getenv('FORUM_DIGEST_TASK_RATE_LIMIT', '6/m')
# limit the size of user batches (cs service pulls / emails sent) per-task 
FORUM_DIGEST_TASK_BATCH_SIZE = int(os.getenv('FORUM_DIGEST_TASK_BATCH_SIZE', 5))
# limit the number of times an individual task will be retried
FORUM_DIGEST_TASK_MAX_RETRIES = 2
# limit the minimum delay between retries of an individual task (in seconds)
FORUM_DIGEST_TASK_RETRY_DELAY = 300
# set the interval (in minutes) at which the top-level digest task is triggered
FORUM_DIGEST_TASK_INTERVAL = int(os.getenv('FORUM_DIGEST_TASK_INTERVAL', 1440))


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
    },
    'formatters': {
        'default': {
            'format': '%(asctime)s [%(levelname)s] [service_name={}] [%(module)s] %(message)s'.format(SERVICE_NAME)
        },
        'rsyslog': {
            'format': ("[service_variant={service_variant}]"
                       "[%(name)s][env:{logging_env}] %(levelname)s "
                       "[{hostname} %(process)d] [%(filename)s:%(lineno)d] "
                       "- %(message)s").format(
                           service_variant=SERVICE_NAME, 
                           logging_env=NOTIFIER_ENV.lower(), 
                           hostname=platform.node().split(".")[0])
        }
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': LOG_LEVEL.upper(),
            'propagate': True
        },
    }
}

CELERYD_HIJACK_ROOT_LOGGER=False

RSYSLOG_ENABLED = os.getenv('RSYSLOG_ENABLED', '')
if RSYSLOG_ENABLED:
    LOGGING['handlers'].update({
        'rsyslog': {
            'level': 'INFO',
            'class': 'logging.handlers.SysLogHandler',
            'address': '/dev/log',
            'formatter': 'rsyslog',
            'facility': logging.handlers.SysLogHandler.LOG_LOCAL0,
        }
    })
    LOGGING['loggers']['']['handlers'].append('rsyslog')

if LOG_FILE:
    LOGGING['handlers'].update({
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'default',
            'filename': LOG_FILE
        },
    })
    LOGGING['loggers']['']['handlers'].append('file')

TIME_ZONE = 'UTC'  # what task workers see
CELERY_TIMEZONE = 'UTC'  # what the main celery process sees 

# set up schedule for forum digest job
if FORUM_DIGEST_TASK_INTERVAL==1440:
    # in the production case, make the 24 hour cycle happen at a 
    # predetermined time of day (midnight UTC).
    DIGEST_CRON_SCHEDULE = {'hour': 0}
else:
    DIGEST_CRON_SCHEDULE = {'minute': '*/{}'.format(FORUM_DIGEST_TASK_INTERVAL) }

DAILY_TASK_MAX_RETRIES = 2
DAILY_TASK_RETRY_DELAY = 60

# Celery / RabbitMQ fine-tuning
# Don't use a connection pool, since connections are dropped by ELB.
BROKER_POOL_LIMIT = 0
BROKER_CONNECTION_TIMEOUT = 1

# When the broker is behind an ELB, use a heartbeat to refresh the
# connection and to detect if it has been dropped.
BROKER_HEARTBEAT = 10.0
BROKER_HEARTBEAT_CHECKRATE = 2

# Each worker should only fetch one message at a time
CELERYD_PREFETCH_MULTIPLIER = 1

LANGUAGE_CODE = os.getenv('NOTIFIER_LANGUAGE', 'en')
LANGUAGES = (
    ("en", "English"),
    ("ar", "Arabic"),
    ("es_419", "Spanish (Latin America)"),
    ("fr", "French"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("pt_BR", "Portuguese (Brazil)"),
    ("ru", "Russian"),
    ("zh_CN", "Chinese (Simplified)"),
)
USE_L10N = True
LOCALE_PATHS = (os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locale'),)

# Parameterize digest logo image url
LOGO_IMAGE_URL = os.getenv('LOGO_IMAGE_URL', "{}/static/images/edx-theme/edx-header-logo.png".format(LMS_URL_BASE))
