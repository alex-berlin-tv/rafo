from pydantic.fields import computed_field
from pydantic.main import BaseModel

import abc
import enum
import re
from typing import ClassVar, Optional, Type, TypeVar




normalize_char_map = {
    ord("ä"): "ae",
    ord("Â"): "Ae",
    ord("ö"): "oe",
    ord("Ô"): "Oe",
    ord("ü"): "ue",
    ord("Û"): "Ue",
    ord("ß"): "ss",
    ord("á"): "a",
    ord("Á"): "A",
    ord("é"): "e",
    ord("É"): "E",
    ord("ó"): "o",
    ord("à"): "a",
    ord("À"): "A",
    ord("è"): "e",
    ord("È"): "E",
    ord("ò"): "o",
    ord("Ò"): "O",
}


def normalize_for_filename(text: str) -> str:
    """
    Normalizes a given string for use within a filename. The returned value
    meets the following requirements:
    - Lowercase.
    - Most in Germany used umlauts, diacritics and similar special characters
      are replaced by an ASCII character.
    - Spaces (everything matching `\r` in a regular expression) are replaced
      with a dash.
    - Every other char which doesn't fulfill the regex `[a-zA-Z0-9-_]` is
      removed.
    """
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = text.translate(normalize_char_map)
    text = re.sub(r"[^a-zA-Z0-9-_]", "", text)
    return text


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
    def _done(
        cls,
        title: str,
        description: str,
        items: Optional[dict[str, str]],
        copy_values: Optional[dict[str, str]] = None,
    ):
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
