"""
This module contains a thin wrapper around the Baserow Client library.
"""

from .config import settings

from typing import List

from baserow.client import ApiError, BaserowClient
from baserow.filter import Column, Filter
from pydantic import BaseModel, ConfigDict


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
    def by_filter(cls, filter: List[Filter]):
        response = Client().list_database_table_rows(
            cls.table_id(),
            filter=filter,
            user_field_names=True,
        )
        if response.count != 1:
            if response.count == 0:
                error = "no"
            else:
                error = "more than one"
            raise RuntimeError(
                f"{error} {cls.table_name()} from table {cls.table_id()} with filter '{filter}' found"
            )
        return cls.model_validate(response.results[0])

    @classmethod
    def by_id(cls, row_id: int):
        response = Client().get_database_table_row(
            cls.table_id(), row_id, user_field_names=True)
        print(response)
        return cls.model_validate(response)

    @classmethod
    def by_uuid(cls, uuid: str):
        return cls.by_filter([Column("UUID").equal(uuid)])

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
