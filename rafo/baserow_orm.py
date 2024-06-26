"""
This module contains a thin wrapper around the Baserow Client library.
"""


import abc
import asyncio
from dataclasses import asdict
from datetime import datetime
import enum
import functools
from io import BufferedReader
from typing import Any, ClassVar, Generic, Optional, Self, Type, TypeVar, Union

from baserow.client import ApiError, BaserowClient
from baserow.filter import Column, Filter
from pydantic import BaseModel, ConfigDict, Field
from pydantic.root_model import RootModel
from pydantic.functional_serializers import model_serializer
from pydantic.functional_validators import model_validator

from rafo.config import settings
from rafo.log import logger


T = TypeVar("T", bound="Table")


class NoSingleResultFoundError(Exception):
    """
    Exception which is thrown if, contrary to the instruction, more than one
    entry is found by a query.
    """
    pass


class NoResultError(Exception):
    """
    If a query is expected to return at least one record but none are found,
    this exception will be thrown.
    """


class RowLink(BaseModel):
    """A single link to another table."""
    row_id: Optional[int] = Field(alias=str("id"))
    key: Optional[str] = Field(alias=str("value"))

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def id_or_value_must_be_set(self: "RowLink") -> "RowLink":
        if self.row_id is None and self.key is None:
            raise ValueError(
                "At least one of the row_id and value fields must be set"
            )
        return self

    @model_serializer
    def serialize(self) -> Union[int, str]:
        """
        Serializes the field into the data structure required by the Baserow
        API. If an entry has both an id and a value set, the id is used.
        Otherwise the key field is used.

        From the Baserow API documentation: Accepts an array containing the
        identifiers or main field text values of the related rows.
        """
        if self.row_id is not None:
            return self.row_id
        if self.key is not None:
            return self.key
        raise ValueError("both fields id and key are unset for this entry")


class TableLinkField(RootModel[list[RowLink]]):
    """
    Table link field. Can contain one or more links to rows in another table.
    """
    root: list[RowLink]

    def id_str(self) -> str:
        """Returns a list of all ID's as string for debugging."""
        return ",".join([str(link.row_id) for link in self.root])


SelectEnum = TypeVar("SelectEnum", bound=enum.Enum)
"""
Instances of a SelectEntry have to be bound to a enum which contain the possible
values of the select entry.
"""


class SelectEntry(BaseModel, Generic[SelectEnum]):
    """A entry in a single or multiple select field."""
    entry_id: Optional[int] = Field(alias="id")
    value: Optional[SelectEnum]
    color: Optional[str]

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def id_or_value_must_be_set(self: "SelectEntry") -> "SelectEntry":
        if self.entry_id is None and self.value is None:
            raise ValueError(
                "At least one of the entry_id and value fields must be set"
            )
        return self

    @model_serializer
    def serialize(self) -> Union[int, str]:
        """
        Serializes the field into the data structure required by the Baserow
        API. If an entry has both an id and a value set, the id is used.
        Otherwise the set field is used.

        From the Baserow API documentation: Accepts an integer or a text value
        representing the chosen select option id or option value. A null value
        means none is selected. In case of a text value, the first matching
        option is selected. 
        """
        if self.entry_id is not None:
            return self.entry_id
        if self.value is not None:
            return self.value.value
        raise ValueError("both fields id and value are unset for this entry")


class SingleSelectField(SelectEntry[SelectEnum]):
    pass


class MultipleSelectField(RootModel[list[SelectEntry]], Generic[SelectEnum]):
    """Multiple select field in a table."""
    root: list[SelectEntry[SelectEnum]]


class FileThumbnail(BaseModel):
    """Thumbnail declaration within file response."""
    url: str
    width: Optional[int]
    height: Optional[int]


class File(BaseModel):
    """A file."""
    url: Optional[str] = None
    mime_type: Optional[str]
    thumbnails: Optional[dict[str, FileThumbnail]] = None
    name: str
    size: Optional[int] = None
    is_image: Optional[bool] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    original_name: Optional[str] = None

    @classmethod
    def upload_file(cls, file: BufferedReader) -> "File":
        """
        Uploads a file to Baserow and returns the result.
        """
        response = Client().upload_file(file)
        return cls.model_validate(asdict(response))

    @classmethod
    def upload_via_url(cls, url: str) -> "File":
        """
        Loads a file from the given URL into Baserow.
        """
        response = Client().upload_via_url(url)
        return cls.model_validate(asdict(response))


class FileField(RootModel[list[File]]):
    """File field which can hold uploaded files."""
    root: list[File]


DurationField = Union[str, int]
"""
The duration can be represented as a string in the format specified in the Field
settings (e.g. 'h:mm') or as an integer representing the total number of
seconds.
"""


class Client(BaserowClient):
    """
    Encapsulates the baserow client into a singleton.
    """
    _instance = None
    __initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if not self.__initialized:
            super().__init__(settings.baserow_url, token=settings.baserow_api_key)
            self.__initialized = True


class Result(Generic[T]):
    """
    Result of a query. Supports additional checking and post-processing of
    results.
    """

    def __init__(self, value: list[T], query_explanation: str = ""):
        """
        The query_explanation provides a clear and understandable explanation of
        the query that the result is based on. It is used in error messages
        generated by the filters. Should complete the sentence "when...".
        """
        self.__value = value
        self.__query_description = query_explanation

    def any(self) -> list[T]:
        """Returns the result as list without any additional checks."""
        return self.__value

    def one(self) -> T:
        """
        Exactly one entry is expected to be within the result. This is useful,
        for example, if you're searching for an existing entry by its unique ID.
        If this requirement is not met, a `NoSingleResultFoundError` is thrown.
        """
        if len(self.__value) == 0:
            raise NoResultError(
                f"empty result when {self.__query_description}, exactly one result expected"  # noqa
            )
        if len(self.__value) > 1:
            raise NoSingleResultFoundError(
                f"more than one result when {self.__query_description}, exactly one result expected"  # noqa
            )
        return self.__value[0]

    def not_none(self) -> list[T]:
        """Returns the result(s) as a list if there is at least one record present."""
        if len(self.__value) == 0:
            raise NoResultError(
                f"expected at least one record when {self.__query_description}, zero results were returned"  # noqa
            )
        return self.__value

    async def is_empty(self) -> bool:
        """Checks whether result contains any results."""
        return len(self.__value) > 0


class Table(BaseModel, abc.ABC):
    """
    Encapsulates the most common interactions with a baserow table by binding it
    to a pydantic BaseModel.

    Baserow provides two ways of accessing or specifying fields. The first is by
    using the unique field ID, which can be obtained in the frontend or by using
    the list table fields call. The second is by using the name given by the
    user in the frontend, also known as the user field name. Currently, the
    model only supports accessing fields using their user field names. These
    names can be provided as field names in the code or by setting an alias for
    a field.
    """

    @property
    @abc.abstractmethod
    def table_id(cls) -> int:  # type: ignore
        """
        The Baserow table ID. Every table in Baserow has a unique ID. This means
        that each model is linked to a specific table. It's not currently
        possible to bind a table model to multiple tables.
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def table_name(cls) -> str:  # type: ignore
        """
        Each table model must have a human-readable table name. The name is used
        for debugging information only and has no role in addressing/interacting
        with the Baserow table. Ideally this should be the same name used for
        the table within the Baserow UI.
        """
        raise NotImplementedError()

    table_id: ClassVar[int]
    table_name: ClassVar[str]

    dump_response: ClassVar[bool] = False
    """
    If set to true, the parsed dict of the body of each API response is dumped
    to debug output.
    """

    dump_payload: ClassVar[bool] = False
    """
    If set to true, the data body for the request is dumped to the debug output.
    """

    @classmethod
    def validate_baserow(cls):
        """
        Checks if the given table id's exist in the Baserow backend. And the given user field
        names exist in the table.
        """
        aliases = [field.alias for _, field in cls.model_fields.items()]
        try:
            result = Client().list_database_table_fields(cls.table_id)
            field_names = [field.name for field in result]
            for alias in aliases:
                if alias not in field_names and alias != "id":
                    raise RuntimeError(
                        f"Field '{alias}' not found in Baserow {cls.table_name} table {cls.table_id}"  # noqa
                    )
        except ApiError as e:
            if e.args[0] == "ERROR_TABLE_DOES_NOT_EXIST":
                raise RuntimeError(
                    f"There is no {cls.table_name} table in baserow for id {cls.table_id}")
            raise e

    @classmethod
    async def query(
        cls: Type[T],
        filter: list[Filter],
    ) -> Result[T]:
        """
        Queries rows in the table If no results are found, the function will
        return `None`. Otherwise, the results will be returned as a list. The
        model instance will only be returned without being encapsulated in a
        list if `one` is set.

        Args:
            filter: List of filter which should be applied to the query. Provide
                empty list if no filtering is desired. 
            one: Set to `True` if exactly one entry is expected to be found.
                This is useful, for example, if you're searching for an existing
                entry by its unique ID. If this requirement is not met, a
                `NoSingleResultFoundError` is thrown. Cannot be set at the same
                time as `not_none`.
            not_none: Use this if you expect your query to return at least one
                record. Will throw a `NoResultError' if the query returns an
                empty result.Cannot be set at the same time as `one`.
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            functools.partial(
                Client().list_database_table_rows,
                cls.table_id,
                filter=filter,
                user_field_names=True,
            )
        )
        if cls.dump_response:
            logger.debug(response)
        return Result(
            [cls.model_validate(result) for result in response.results],
            f"querying  table {cls.table_id} ({cls.table_name}) with filter '{filter}'",  # noqa
        )

    @classmethod
    async def filter(cls: Type[T], **kwargs) -> Result[T]:
        """
        Filters for entries whose fields equals the specified values. Note that
        this method does not allow you to query for records by their unique ID.
        """
        filters: list[Filter] = []
        for key, value in kwargs.items():
            # Check, whether the submitted key-value pairs are in the model and
            # the value passes the validation specified by the field.
            cls.__validate_single_field(key, value)

            # Constructs the filter using the alias, if it exists.
            filter_key = key
            alias = cls.model_fields[key].alias  # One for the type checking.
            if alias is not None:
                filter_key = alias
            filters.append(Column(filter_key).equal(value))
        return await cls.query(filters)

    @classmethod
    async def by_uuid(cls: Type[T], uuid: str) -> Result[T]:
        logger.debug(f"baserow query in {cls.table_name} by UUID {uuid}")
        return await cls.query([Column("UUID").equal(uuid)])

    @classmethod
    async def by_id(cls: Type[T], row_id: int) -> Result[T]:
        """
        Retrieve an entry by its unique row ID.
        """
        logger.debug(f"baserow query in {cls.table_name} by ID {row_id}")
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            functools.partial(
                Client().get_database_table_row,
                cls.table_id,
                row_id,
                user_field_names=True,
            )
        )
        if cls.dump_response:
            logger.debug(response)
        return Result(
            [cls.model_validate(response)],
            f"querying the table with the unique ID '{row_id}' for {cls.table_name} ({cls.table_id})",  # noqa
        )

    @staticmethod
    async def test():
        await asyncio.sleep(1)

    @classmethod
    async def by_link_field(
        cls: Type[T],
        link_field: TableLinkField,
    ) -> Result[T]:
        """
        Get entries by a TableLinkField values. Used to retrieve linked table rows.

        Args:
            one: Set to `True` if exactly one entry is expected to be found.
                This is useful, for example, if you're searching for an existing
                entry by its unique ID. If this requirement is not met, a
                `NoSingleResultFoundError` is thrown. Cannot be set at the same
                time as `not_none`.
            not_none: Use this if you expect your query to return at least one
                record. Will throw a `NoResultError' if the query returns an
                empty result.Cannot be set at the same time as `one`.
        """
        description = f"query in {cls.table_name} for linked fields with ID's [{link_field.id_str()}]"  # noqa
        logger.debug(
            f"baserow {description}"
        )
        coroutines = []
        for link in link_field.root:
            if link.row_id is not None:
                coroutines.append(cls.by_id(link.row_id))
            else:
                raise NotImplementedError(
                    "retrieving linked rows via their key value is currently not implemented by this method"
                )
        cr_rsl = await asyncio.gather(
            *coroutines,
            return_exceptions=True,
        )

        rsl: list[T] = []
        try:
            for item in cr_rsl:
                if isinstance(item, BaseException):
                    raise item
                rsl.append(item.one())
            return Result(rsl, description)
        except NoSingleResultFoundError as e:
            raise NoSingleResultFoundError(
                f"error while {description}, {e}")
        except NoResultError as e:
            raise NoResultError(
                f"error while {description}, {e}")

    def create(self) -> Self:
        """
        Creates a new row in the Baserow table using the values of the instance.
        Returns the object of Baserow's response.
        """
        rsl = Client().create_database_table_row(
            self.table_id,
            self.model_dump(by_alias=True, mode="json", exclude_none=True),
            user_field_names=True
        )
        return self.model_validate(rsl)

    @classmethod
    def update(cls, row_id: int, by_alias: bool = True, **kwargs: Any):
        """
        Update the fields in the database specified by the kwargs parameter. The
        keys provided must be valid field names in the model. values will be
        validated against the model. If the value type is inherited by the
        BaseModel, its serializer will be applied to the value and submitted to
        the database. Please note that custom _Field_ serializers for any other
        types are not taken into account.

        The custom model serializer is used in the module because the structure
        of some Baserow fields differs between the GET result and the required
        POST data for modification. For example, the MultipleSelectField returns
        ID, text value, and color with the GET request. However, only a list of
        IDs or values is required for updating the field using a POST request.

        Args:
            row_id: ID of row in Baserow to be updated.
            by_alias: Specify whether to use alias values to address field names
                in Baserow. Note that this value is set to True by default,
                contrary to pydantic's usual practice. In the context of the
                table model (which is specifically used to represent Baserow
                tables), setting an alias typically indicates that the field
                name in Baserow is not a valid Python variable name.
        """
        payload = cls.__model_dump_subset(by_alias, **kwargs)
        if cls.dump_payload:
            logger.debug(payload)
        Client().update_database_table_row(
            cls.table_id,
            row_id,
            payload,
            user_field_names=True,
        )

    @classmethod
    def batch_update(cls, data: dict[int, dict[str, Any]], by_alias: bool = True):
        """
        Updates multiple fields in the database. The given data dict must map
        the unique row id to the data to be updated. The input is validated
        against the model. See the update method documentation for more
        information about its limitations and underlying ideas.

        Args:
            data: A dict mapping the unique row id to the data to be updated.
            by_alias: Please refer to the documentation on the update method to
                learn more about this arg.
        """
        payload = []
        for key, value in data.items():
            entry = cls.__model_dump_subset(by_alias, **value)
            entry["id"] = key
            payload.append(entry)
        if cls.dump_payload:
            logger.debug(payload)
        raise NotImplementedError(
            "Baserow client library currently does not support batch update operations on rows"
        )

    @classmethod
    def __validate_single_field(cls, field_name: str, value: Any) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any] | None, set[str]]:
        return cls.__pydantic_validator__.validate_assignment(
            cls.model_construct(), field_name, value
        )

    @classmethod
    def __model_dump_subset(cls, by_alias: bool, **kwargs: Any) -> dict[str, Any]:
        """
        This method takes a dictionary of keyword arguments (kwargs) and
        validates it against the model before serializing it as a dictionary. It
        is used for the update and batch_update methods. If a field value is
        inherited from a BaseModel, it will be serialized using model_dump.

        Please refer to the documentation on the update method to learn more
        about its limitations and underlying ideas.
        """
        rsl = {}
        for key, value in kwargs.items():
            # Check, whether the submitted key-value pairs are in the model and
            # the value passes the validation specified by the field.
            cls.__validate_single_field(key, value)

            # If a field has an alias, replace the key with the alias.
            rsl_key = key
            alias = cls.model_fields[key].alias
            if by_alias and alias:
                rsl_key = alias

            # When the field value is a pydantic model, serialize it.
            rsl[rsl_key] = value
            if isinstance(value, BaseModel):
                rsl[rsl_key] = value.model_dump(by_alias=by_alias)
        return rsl
