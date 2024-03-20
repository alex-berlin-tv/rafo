"""
Handles the interactions with Omnia.
"""

from .omnia import *

from typing import Optional

from pydantic.main import BaseModel


class Notification(BaseModel):
    """
    Notification sent via server-sent-events. Used to update the user about long
    running processes.
    """
    target: str
    title: str
    state: str
    description: str
    items: Optional[dict[str, str]]
