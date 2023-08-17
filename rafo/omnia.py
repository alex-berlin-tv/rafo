from re import A
from .config import settings
from .log import logger

from enum import Enum
import hashlib
from typing import Any, Optional

from pydantic import BaseModel, Field
import requests


BASE_URL: str = "https://api.nexx.cloud/v3.1/"
OMNIA_HEADER_X_REQUEST_CID: str = "X-Request-CID"
OMNIA_HEADER_X_REQUEST_TOKEN: str = "X-Request-Token"


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


class Response(BaseModel):
    metadata: ResponseMetadata
    result: Any = None
    paging: Optional[ResponsePaging] = None


class StreamType(str, Enum):
    VIDEO_STREAM_TYPE = "videos"
    AUDIO_STREAM_TYPE = "audio"
    SHOW_STREAM_TYPE = "shows"


class ApiType(str, Enum):
    MEDIA = "media"
    MANAGEMENT = "management"
    UPLOAD_LINK_MANAGEMENT = "upload_link_management"
    SYSTEM = "system"
    DOMAIN = "domain"


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

    def by_id(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str] = {},
    ):
        """Return a item of a given stream type by it's id."""
        return self.call(
            "get",
            stream_type,
            ApiType.MEDIA,
            "byid",
            [str(item_id)],
            parameters,
        )
    
    def upload_by_url(
        self,
        stream_type: StreamType,
        url: str,
        use_queue: bool,
        filename: Optional[str] = None,
    ):
        """
        will create a new Media Item of the given Streamtype, if the given
        urlParameter contains a valid Source for the given Streamtype.
        """
        data = {
            "url": url,
            "useQueue": 1 if use_queue else 0,
        }
        if filename:
            data["filename"] = filename
        return self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "fromurl",
            [],
            data
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
                BASE_URL, self.domain_id, stream_type.value, operation, args_str)
        elif api_type is ApiType.MANAGEMENT:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "manage", stream_type, args_str, operation)
        elif api_type is ApiType.UPLOAD_LINK_MANAGEMENT:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "manage", "uploadlinks", operation)
        elif api_type is ApiType.SYSTEM:
            url = self.__url_builder(
                BASE_URL, self.domain_id, "system", operation, args_str)
        header = self.__request_header(
            operation, self.domain_id, self.api_secret, self.session_id)
        logger.debug(
            f"About to send {method} to {url} with header {header} and params {parameters}")
        result = requests.request(
            method,
            headers=header,
            url=url,
            data=parameters,
        )
        print(result.json())
        return Response.model_validate(result.json())

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
