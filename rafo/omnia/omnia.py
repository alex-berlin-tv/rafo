import asyncio

from attr import dataclass
from baserow.filter import Date
from typed_settings.types import OptionName
from ..config import settings
from ..log import logger

from datetime import datetime
from enum import Enum
import hashlib
from typing import Any, Optional, Union

import aiohttp
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


class QueryMode(str, Enum):
    CLASSIC_WITH_AND = "classicwithand"
    CLASSIC_WITH_OR = "classicwithor"
    FULL_TEXT = "fulltext"
    """Lucene Search with Relevance."""


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
    description: Optional[str] = Field(
        alias="description", default=None)  # Additional field
    release_date: Optional[Date] = Field(
        alias="releasedate", default=None)  # Additional field


class ConnectedMedia(BaseModel):
    item_id: int = Field(alias="ID")
    gid: int = Field(alias="GID")
    hash_value: str = Field(alias="hash")
    title: str = Field(alias="title")


class PublishingData(BaseModel):
    valid_from_desktop: Optional[datetime] = Field(
        alias="validFromDesktop", default=None)
    valid_until_desktop: Optional[datetime] = Field(
        alias="validUntilDesktop", default=None)
    valid_from_mobile: Optional[datetime] = Field(
        alias="validFromMobile", default=None)
    valid_until_mobile: Optional[datetime] = Field(
        alias="validUntilMobile", default=None)


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
    image_data: Any = Field(alias="imagedata")
    publishing_data: Optional[PublishingData] = Field(
        alias="publishingdata", default=None
    )
    connected_media: Optional[dict[str, list[ConnectedMedia]]] = Field(
        alias="connectedmedia", default=None,
    )


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

    async def upload_by_url(
        self,
        stream_type: StreamType,
        url: str,
        use_queue: bool,
        data: dict[str, str],
        filename: Optional[str] = None,
        ref_nr: Optional[str] = None,
        auto_publish: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> Response:
        """
        will create a new Media Item of the given Streamtype, if the given
        urlParameter contains a valid Source for the given Streamtype.
        """
        data["url"] = url
        data["useQueue"] = "1" if use_queue else "0"
        if filename:
            data["filename"] = filename
        if ref_nr:
            data["refnr"] = ref_nr
        if auto_publish is not None:
            data["autoPublish"] = "1" if auto_publish else "0"
        if notes is not None:
            data["notes"] = notes
        return await self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "fromurl",
            [],
            data
        )

    async def by_id(
        self,
        stream_type: StreamType,
        item_id: int,
        add_publishing_details: bool,
        parameters: dict[str, str] = {},
    ) -> Response:
        """
        Return a item of a given stream type by it's id. Use
        `add_publishing_details` in order to also query for inactive/unpublished
        objects.
        """
        if add_publishing_details:
            parameters["addPublishingDetails"] = "1"
        return await self.call(
            "get",
            stream_type,
            ApiType.MEDIA,
            "byid",
            [str(item_id)],
            {},
            params=parameters,
        )

    async def by_reference(
        self,
        stream_type: StreamType,
        ref_nr: str,
        add_publishing_details: bool,
    ) -> Response:
        """
        Return all items with a given reference number. Use
        `add_publishing_details` in order to also query for inactive/unpublished
        objects.
        """
        parameters: dict[str, str] = {}
        if add_publishing_details:
            parameters["addPublishingDetails"] = "1"
        return await self.call(
            "get",
            stream_type,
            ApiType.MEDIA,
            "byreference",
            [ref_nr],
            {},
            params=parameters,
        )

    async def by_query(
        self,
        stream_type: StreamType,
        query: str,
        query_mode: QueryMode,
        query_fields: list[str],
        include_substring_matches: bool,
        add_publishing_details: bool,
        minimal_query_score: Optional[int] = None,
        skip_reporting: Optional[bool] = None,
    ) -> Response:
        """
        Performs a regular Query on all Items. The "order" Parameters are
        ignored, if query-mode is set to "fulltext".

        Args:
            query: The search term. stream_type: As usual. query_mode: Defines
                the Way, the Query is executed. Fore more results,
                "classicwithor" is optimal. For a Lucene Search with Relevance,
                use "fulltext".
            query_fields: A comma separated List of Attributes, to search
                within. If omitted, the Search will use all available Text
                Attributes.
            include_substring_matches: By default, the Query will only return
                Results on full Words. If also Substring Matches shall be
                returned, set this Parameter to 1. Only useful, if query-mode is
                not "fulllext".
            add_publishing_details: Add an Object of Publishing States and
                Restrictions to each Item. When adding this Output Modifier, it
                is possible (and that's he only accepted way) to query for
                inactive/unpublished Objects. 
            minimal_query_score: Skip Results with a Query Score
                lower than the given Value. Only useful for query-mode
                "fulltext".
            skip_reporting: if set to 0 or omitted, the Call will implicitly
                report this Query to the Omnia Reporting System.
        """
        data: dict[str, str] = {}
        data["addPublishingDetails"] = "1" if add_publishing_details else "0"
        data["queryMode"] = query_mode.value
        data["queryFields"] = ",".join(query_fields)
        data["includeSubstringMatches"] = "1" if include_substring_matches else "0"
        if minimal_query_score is not None:
            data["minimalQueryScore"] = str(minimal_query_score)
        if skip_reporting is not None:
            data["skipReporting"] = "1" if skip_reporting else "0"

        return await self.call(
            "get",
            stream_type,
            ApiType.MEDIA,
            "byquery",
            [query],
            data,
            # params=data,
        )

    async def update(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str],
    ) -> Response:
        """
        Will update the general Metadata of a Media Item. Uses the Management API.
        """
        return await self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT,
            "update",
            [str(item_id)],
            parameters
        )

    async def update_restrictions(
        self,
        stream_type: StreamType,
        item_id: int,
        parameters: dict[str, str],
    ) -> Response:
        """
        Will update the restrictions of a Media Item. Uses the Management API.
        """
        return await self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT,
            "updaterestrictions",
            [str(item_id)],
            parameters
        )

    async def update_cover(self, stream_type: StreamType, item_id: int, url: str) -> Response:
        """Upload and set a cover from a given URL."""
        return await self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "cover",
            [str(item_id)],
            {
                "url": url,
            },
        )

    async def approve(self, stream_type: StreamType, item_id: int, parameters: dict[str, str]) -> Response:
        """Approve an item."""
        return await self.call(
            "post",
            stream_type,
            ApiType.MANAGEMENT,
            "approve",
            [str(item_id)],
            parameters,
        )

    async def connect_show(self, stream_type: StreamType, item_id: int, show_id: int) -> Response:
        """Connect a media item with a given show."""
        return await self.call(
            "put",
            stream_type,
            ApiType.MANAGEMENT_CONNECT,
            "connectshow",
            [str(item_id), str(show_id)],
            {},
        )

    async def editable_attributes_for(self, stream_type: StreamType) -> Response:
        """Returns a list of editable attributes for a given stream type."""
        return await self.call(
            "get",
            stream_type,
            ApiType.SYSTEM,
            "editableattributesfor",
            [stream_type],
            {}
        )

    async def editable_restrictions_for(self, stream_type: StreamType) -> Response:
        """Returns a list of editable restrictions for a given stream type."""
        return await self.call(
            "get",
            stream_type,
            ApiType.SYSTEM,
            "editablerestrictionsfor",
            [stream_type],
            {}
        )

    async def call(
        self,
        method: str,
        stream_type: StreamType,
        api_type: ApiType,
        operation: str,
        args: list[str],
        data: dict[str, str],
        params: dict[str, str] = {},
    ) -> Response:
        """Generic call to the Omnia Media API. Won't work with the management API's."""
        return await self.__universal_call(
            method, stream_type, api_type, operation, args, data, params=params
        )

    async def __universal_call(
        self,
        method: str,
        stream_type: StreamType,
        api_type: ApiType,
        operation: str,
        args: list[str],
        data: dict[str, str],
        params: dict[str, str] = {},
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
            f"About to send {method} to {url} with header {header}, params {params}, and data {data}"
        )
        await asyncio.sleep(.1)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                headers=header,
                data=data,
                params=params,
            ) as response:
                response_json = await response.json()
                return Response.model_validate(response_json, strict=False)

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

    @staticmethod
    def convert_dateformat(time: datetime) -> str:
        """
        Converts a given datetime object into the time representation of Omnia.
        Integer Unix timestamp as string.
        """
        return str(int(time.timestamp()))
