from __future__ import absolute_import
from __future__ import unicode_literals
import logging

logger = logging.getLogger(__name__)

# silence chatty logging from urllib3 via requests
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARN)

