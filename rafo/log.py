import logging

from rafo.config import settings


logging.basicConfig(level=str(settings.log_level).upper())
logger = logging.getLogger()
