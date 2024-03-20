from ..config import settings
from ..log import logger

from datetime import datetime
from enum import Enum
import hashlib
from typing import Any, Optional, Union

from pydantic import BaseModel, Field
import requests


BASE_URL: str = "https://api.nexx.cloud/v3.1/"
OMNIA_HEADER_X_REQUEST_CID: str = "X-Request-CID"
OMNIA_HEADER_X_REQUEST_TOKEN: str = "X-Request-Token"


class Bool(int, Enum):
    FALSE = 0
    TRUE = 1

    def to_bool(self) -> bool:
        if self is self.FALSE:
            return False
        return True


class StreamType(str, Enum):
    VIDEO = "videos"
    AUDIO = "audio"
    SHOW = "shows"


class ApiType(str, Enum):
    MEDIA = "media"
    MANAGEMENT = "management"
    MANAGEMENT_CONNECT = "management_connect"
    UPLOAD_LINK_MANAGEMENT = "upload_link_management"
    SYSTEM = "system"
    DOMAIN = "domain"


class ResponseMetadata(BaseModel):
    """Metadata part of an API response."""

    status: int = Field(alias="status")
    """The HTTP Status for this Call."""
    api_version: Optional[str] = Field(None, alias="apiversion")
    """Version of the API."""
    verb: str = Field(alias="verb")
    """The used HTTP Verb."""
    processing_time: float = Field(alias="processingtime")
    """Internal Duration, needed to create the response."""
    called_with: Optional[str] = Field(None, alias="calledwith")
    """The called Endpoint and Parameter."""
    called_for: Optional[str] = Field(None, alias="calledfor")
    """The `cfo` Parameter from the API Call."""
    for_domain: Optional[int] = Field(None, alias="fordomain")
    """The calling Domain ID."""
    from_stage: Optional[int] = Field(None, alias="fromstage")
    """The result was created by a Stage or Productive Server."""
    notice: Optional[str] = Field(None, alias="notice")
    """
    If the Call uses deprecated Functionality, find here a Hint, what Attributes
    should be changed.
    """
    error_hint: Optional[str] = Field(None, alias="errorhint")
    """If the Call failed, a Hint for the Failure Reason."""
    from_cache: Optional[int] = Field(None, alias="fromcache")
    """States whether result came from cache"""

    class Config:
        populate_by_name = True


class ResponsePaging(BaseModel):
    """Information on the paging of an result."""

    start: int = Field(alias="start")
    """The Start of the Query Range."""
    limit: int = Field(alias="limit")
    """The given maximal Item List Length."""
    result_count: int = Field(alias="resultcount")
    """The maximally available Number of Items."""

    class Config:
        populate_by_name = True


class MediaResultGeneral(BaseModel):
    item_id: int = Field(alias="ID")
    gid: int = Field(alias="GID")
    hash_value: str = Field(alias="hash")
    title: str = Field(alias="title")
    subtitle: str = Field(alias="subtitle")
    genre_raw: Optional[str] = Field(alias="genre_raw", default=None)
    genre: Optional[str] = Field(alias="genre", default=None)
    content_moderation_aspects: Optional[str] = Field(
        alias="contentModerationAspects", default=None)
    uploaded: Optional[datetime] = Field(alias="uploaded", default=None)
    created: datetime = Field(alias="created")
    audio_type: Optional[str] = Field(alias="audiotype", default=None)
    runtime: Optional[str] = Field(alias="runtime", default=None)
    is_picked: Bool = Field(alias="isPicked")
    for_kids: Optional[Bool] = Field(alias="forKids", default=None)
    is_pay: Optional[Bool] = Field(alias="isPay", default=None)
    is_ugc: Optional[Bool] = Field(alias="isUGC", default=None)


class ItemUpdate(BaseModel):
    stream_type: StreamType = Field(alias="streamtype")
    generated_id: int = Field(alias="generatedID")
    generated_gid: int = Field(alias="generatedGID")


class ManagementResult(BaseModel):
    message: str
    item_update: Optional[ItemUpdate] = Field(alias="itemupdate", default=None)
    operation_id: Optional[int] = Field(alias="operationid", default=None)


class MediaResult(BaseModel):
    general: MediaResultGeneral = Field(alias="general")
    # image_data: MediaResultImageData = Field(alias="imagedata")
    image_data: Any = Field(alias="imagedata")


class Response(BaseModel):
    metadata: ResponseMetadata
    result: Union[ManagementResult, MediaResult,
                  list[MediaResult], None] = None
    paging: Optional[ResponsePaging] = None


class Omnia:
    def __init__(
        self,
        domain_id: str,
        api_secret: str,
        session_id: str,
    ):
        self.domain_id = domain_id
        self.api_secret = api_secret
        self.session_id = session_id

    @classmethod
    def from_config(cls):
        return cls(
            settings.omnia_domain_id,
            settings.omnia_api_secret,
            settings.omnia_session_id
        )

    def upload_by_url(
        self,
        stream_type: StreamType,
        url: str,
        use_queue: bool,
        parameters: dict[str, str],
        filename: Optional[str] = None,
        ref_nr: Optional[str] = None,
        auto_publish: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> Response:
        """
        will create a new Media Item of the given Streamtype, if the given
        urlParameter contains a valid Source for the given Streamtype.
        """
        parameters["url"] = url
        parameters["useQueue"] = "1" if use_queue else "0"
        if filename:
            parameters["filename"] = filename
        if ref_nr:
            parameters["refnr"] = ref_nr
        if auto_publish is not None:
            parameters["autoPublish"] = "1" if auto_publish else "0"
        if notes is not None:
            parameters["notes"] = notes
        return self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "fromurl",
            [],
            parameters
        )

    def by_id(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str] = {},
    ) -> Response:
        """Return a item of a given stream type by it's id."""
        return self.call(
            "get",
            stream_type,
            ApiType.MEDIA,
            "byid",
            [str(item_id)],
            parameters,
        )

    def update(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str],
    ) -> Response:
        """
        Will update the general Metadata of a Media Item. Uses the Management API.
        """
        return self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT,
            "update",
            [str(item_id)],
            parameters
        )

    def update_restrictions(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str],
    ) -> Response:
        """
        Will update the restrictions of a Media Item. Uses the Management API.
        """
        return self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT,
            "updaterestrictions",
            [str(item_id)],
            parameters
        )

    def update_cover(self, stream_type: StreamType, item_id: int, url: str) -> Response:
        """Upload and set a cover from a given URL."""
        return self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "cover",
            [str(item_id)],
            {
                "url": url,
            },
        )

    def approve(self, stream_type: StreamType, item_id: int, parameters: dict[str, str]) -> Response:
        """Approve an item."""
        return self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "approve",
            [str(item_id)],
            parameters,
        )

    def connect_show(self, stream_type: StreamType, item_id: int, show_id: int) -> Response:
        """Connect a media item with a given show."""
        return self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT_CONNECT,
            "connectshow",
            [str(item_id), str(show_id)],
            {},
        )

    def editable_attributes_for(self, stream_type: StreamType) -> Response:
        """Returns a list of editable attributes for a given stream type."""
        return self.call(
            "get",
            stream_type,
            ApiType.SYSTEM,
            "editableattributesfor",
            [stream_type],
            {}
        )

    def editable_restrictions_for(self, stream_type: StreamType) -> Response:
        """Returns a list of editable restrictions for a given stream type."""
        return self.call(
            "get",
            stream_type,
            ApiType.SYSTEM,
            "editablerestrictionsfor",
            [stream_type],
            {}
        )

    def call(
        self,
        method: str,
        stream_type: StreamType,
        api_type: ApiType,
        operation: str,
        args: list[str],
        parameters: dict[str, str]
    ) -> Response:
        """Generic call to the Omnia Media API. Won't work with the management API's."""
        return self.__universal_call(
            method, stream_type, api_type, operation, args, parameters
        )

    def __universal_call(
        self,
        method: str,
        stream_type: StreamType,
        api_type: ApiType,
        operation: str,
        args: list[str],
        parameters: dict[str, str],
    ) -> Response:
        args_str = "/".join(args)
        url: str = ""
        if api_type is ApiType.MEDIA:
            url = self.__url_builder(
                BASE_URL, self.domain_id, stream_type.value, operation, args_str
            )
        elif api_type is ApiType.MANAGEMENT:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "manage", stream_type.value, args_str, operation
            )
        elif api_type is ApiType.MANAGEMENT_CONNECT:
            if len(args) < 2:
                raise ValueError(
                    f"management connect calls need at least two args but only {len(args)} given"
                )
            args_tail = args[1:]
            url = self.__url_builder(
                BASE_URL,
                self.domain_id,
                "manage",
                stream_type.value,
                args[0],
                operation,
                "/".join(args_tail),
            )
        elif api_type is ApiType.UPLOAD_LINK_MANAGEMENT:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "manage", "uploadlinks", operation
            )
        elif api_type is ApiType.SYSTEM:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "system", operation, args_str
            )
        header = self.__request_header(
            operation, self.domain_id, self.api_secret, self.session_id
        )
        logger.debug(
            f"About to send {method} to {url} with header {header} and params {parameters}")
        result = requests.request(
            method,
            headers=header,
            url=url,
            data=parameters,
        )
        print(result.json())
        return Response.model_validate(result.json(), strict=False)

    def __request_header(
        self,
        operation: str,
        domain_id: str,
        api_secret: str,
        session_id: str,
    ) -> dict[str, str]:
        signature = hashlib.md5(
            f"{operation}{domain_id}{api_secret}".encode("utf-8"))
        return {
            OMNIA_HEADER_X_REQUEST_CID: session_id,
            OMNIA_HEADER_X_REQUEST_TOKEN: signature.hexdigest(),
        }

    @staticmethod
    def __url_builder(*args) -> str:
        rsl: list[str] = []
        for arg in args:
            rsl.append(str(arg).lstrip("/").rstrip("/"))
        return "/".join(rsl)
