"""
Handles the interactions with Omnia.
"""

import enum
import abc
from typing import ClassVar, Optional, Type, TypeVar

from pydantic.fields import computed_field
from pydantic.main import BaseModel


class NotificationState(str, enum.Enum):
    RUNNING = "running"
    DONE = "done"
    WARNING = "warning"
    ERROR = "error"


T = TypeVar("T", bound="Notification")


class Notification(BaseModel):
    """
    Notification sent via server-sent-events. Used to update the user about long
    running processes.
    """
    @computed_field
    @property
    @abc.abstractmethod
    def target(cls) -> str:  # type: ignore
        raise NotImplementedError()

    target: ClassVar[str]
    state: NotificationState
    title: str
    description: str
    items: Optional[dict[str, str]]
    copy_values: Optional[dict[str, str]]

    @classmethod
    @abc.abstractmethod
    def error(cls: Type[T], e: Exception) -> T:
        pass

    @classmethod
    def from_exception(cls, e: Exception, title: str):
        return cls._error(title, str(e), None)

    @classmethod
    def _running(cls, title: str, description: str, items: Optional[dict[str, str]]):
        return cls(
            state=NotificationState.RUNNING,
            title=title,
            description=description,
            items=items,
            copy_values=None,
        )

    @classmethod
    def _done(cls, title: str, description: str, items: Optional[dict[str, str]], copy_values: Optional[dict[str, str]] = None):
        return cls(
            state=NotificationState.DONE,
            title=title,
            description=description,
            items=items,
            copy_values=copy_values,
        )

    @classmethod
    def _warning(cls, title: str, description: str, items: Optional[dict[str, str]]):
        return cls(
            state=NotificationState.WARNING,
            title=title,
            description=description,
            items=items,
            copy_values=None,
        )

    @classmethod
    def _error(cls, title: str, description: str, items: Optional[dict[str, str]]):
        return cls(
            state=NotificationState.ERROR,
            title=title,
            description=description,
            items=items,
            copy_values=None,
        )

    def to_message(self) -> str:
        """Returns as a message for the SSE event source."""
        return f"data: {self.model_dump_json()}\n\n"
