"""
This module contains a thin wrapper around the Baserow Client library.
"""

from .config import settings
from .log import logger

from typing import List, Optional, Type, TypeVar, Union

from baserow.client import ApiError, BaserowClient
from baserow.filter import Column, Filter
from pydantic import BaseModel, ConfigDict, Field
from pydantic.root_model import RootModel


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
    row_id: int = Field(alias="id")
    key: Optional[str] = Field(alias="value")


class TableLinkField(RootModel[list[RowLink]]):
    """
    Table link field. Can contain one or more links to rows in another table.
    """
    root: list[RowLink]

    def id_str(self) -> str:
        """Returns a list of all ID's as string for debugging."""
        return ",".join([str(link.row_id) for link in self.root])


class Client(BaserowClient):
    """
    Encapsulates the baserow client into a singleton and provides some extra validation methods.
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


class TableConfig(ConfigDict):
    """
    This is a ConfigDict extension that includes custom settings for connecting with Baserow.
    """
    table_id: int
    table_name: str


class Table(BaseModel):
    """
    Encapsulates the most common interactions with a baserow table by binding it to a pydantic
    BaseModel.
    """

    @classmethod
    def validate_baserow(cls):
        """
        Checks if the given table id's exist in the Baserow backend. And the given user field
        names exist in the table.
        """
        table_id = cls.table_id()
        table_name = cls.table_name()
        aliases = [field.alias for _, field in cls.model_fields.items()]
        try:
            result = Client().list_database_table_fields(table_id)
            field_names = [field.name for field in result]
            for alias in aliases:
                if alias not in field_names and alias != "id":
                    raise RuntimeError(
                        f"Field '{alias}' not found in Baserow {table_name} table {table_id}"
                    )
        except ApiError as e:
            if e.args[0] == "ERROR_TABLE_DOES_NOT_EXIST":
                raise RuntimeError(
                    f"There is no {table_name} table in baserow for id {table_id}")
            raise e

    @classmethod
    def query(
        cls: Type[T],
        filter: List[Filter],
        one: bool = False,
        not_none: bool = False,
    ) -> Union[List[T], T, None]:
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
        if one and not_none:
            raise ValueError(
                "The 'one' and 'not_none' parameters cannot both be true in the query method."
            )

        response = Client().list_database_table_rows(
            cls.table_id(),
            filter=filter,
            user_field_names=True,
        )

        if one and response.count != 1:
            raise NoSingleResultFoundError(
                f"when querying table {cls.table_id()} ({cls.table_name()}) with filter '{filter}', only one record was expected, but {response.count} results were returned instead."
            )
        if not_none and response.count < 1:
            raise NoResultError(
                f"expected at least one record when querying table {cls.table_id()} ({cls.table_name()}) with filter '{filter}'. However, zero results were returned instead."
            )

        if one:
            return cls.model_validate(response.results[0])
        if response.count == 0:
            return None
        return [cls.model_validate(result) for result in response.results]

    @classmethod
    def by_uuid(cls: Type[T], uuid: str) -> T:
        logger.debug(f"baserow query in {cls.table_name()} by UUID {uuid}")
        return cls.query([Column("UUID").equal(uuid)], one=True)

    @classmethod
    def by_id(cls: Type[T], row_id: int, not_none: bool = False) -> T:
        """
        Retrieve an entry by its unique row ID. To raise an error when the ID
        does not exist, set `not_none` to `True`.
        """
        logger.debug(f"baserow query in {cls.table_name()} by ID {row_id}")
        response = Client().get_database_table_row(
            cls.table_id(),
            row_id,
            user_field_names=True,
        )
        if not_none and len(response) == 0:
            raise NoResultError(
                f"when querying the table with the unique ID '{row_id}' for {cls.table_name()} ({cls.table_id()}), no resulting entry was found"
            )
        return cls.model_validate(response)

    @classmethod
    def by_link_field(cls: Type[T], link_field: TableLinkField) -> List[T]:
        logger.debug(
            f"baserow query in {cls.table_name()} for linked fields with ID's [{link_field.id_str()}]"
        )
        rsl: List[T] = []
        for link in link_field.root:
            rsl.append(cls.by_id(link.row_id, not_none=True))
        return rsl

    @classmethod
    def table_id(cls) -> int:
        rsl = cls.model_config.get('table_id')
        if not isinstance(rsl, int):
            raise RuntimeError(f"table_id is not configured in a table model")
        return rsl

    @classmethod
    def table_name(cls):
        rsl = cls.model_config.get('table_name')
        if not isinstance(rsl, str):
            raise RuntimeError(
                f"table_name is not configured in a table model"
            )
        return rsl

    def add(self):
        Client().create_database_table_row(
            self.table_id(),
            self.model_dump(by_alias=True),
            user_field_names=True
        )
