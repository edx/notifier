import logging

logger = logging.getLogger(__name__)

# silence chatty logging from urllib3 via requests
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARN)

