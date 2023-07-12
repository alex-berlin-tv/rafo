from .config import settings

import logging


logging.basicConfig(level=str(settings.log_level).upper())

logger = logging.getLogger()