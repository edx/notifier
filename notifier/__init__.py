import logging

from django.conf import settings
from dogapi import dog_stats_api

logger = logging.getLogger(__name__)

if settings.DATADOG_API_KEY:
    logger.info("Initializing datadog")
    dog_stats_api.start(api_key=settings.DATADOG_API_KEY, statsd=True)
else:
    logger.info("No datadog API key found, skipping datadog init")

# silence chatty logging from urllib3 via requests
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARN)

