from config import settings

from typing import Any, Optional
from datetime import datetime

from nocodb.nocodb import APIToken, NocoDBProject, WhereFilter
from nocodb.filters import EqFilter
from nocodb.infra.requests_client import NocoDBRequestsClient
from pydantic import BaseModel, Field


class AnyOf(WhereFilter):
    def __init__(self, column_name, values: list[str]):
        self.__column_name = column_name
        self.__values = values
    
    def get_where(self) -> str:
        value_encoded = ",".join(self.__values)
        return f"({self.__column_name},allof,{value_encoded})"


def get_nocodb_data(project_name: str, table_name: str, filter_obj: Optional[WhereFilter] = None) -> Any:
    token = settings["nocodb_api_key"]
    if not isinstance(token, str):
        raise ValueError("invalid nocodb token, not a string")
    client = NocoDBRequestsClient(
        APIToken(token),  # type: ignore
        settings["nocodb_url"],
    )
    project = NocoDBProject("noco", project_name)
    return client.table_row_list(
        project,
        table_name,
        filter_obj=filter_obj,
    )


class NocoProducer(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    first_name: str = Field(alias="Vorname")
    last_name: str = Field(alias="Name")
    ident: str = Field(alias="Ident")
    email: str = Field(alias="Email")
    uuid: str = Field(alias="UUID")


class NocoShow(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    ident: str = Field(alias="Ident")
    uuid: str = Field(alias="UUID")
    name: str = Field(alias="Name")
    description: Optional[str] = Field(alias="Description")


class NocoShows(BaseModel):
    __root__: list[NocoShow]

    @classmethod
    def from_nocodb(cls, ids: Optional[list[int]] = None):
        if ids is None:
            raise NotImplementedError("getting shows without id is not implemented sorry")
        raw = get_nocodb_data(
            settings["project_name"],
            settings["show_table"],
        )
        data = cls.parse_obj(raw["list"])
        filtered = NocoShows(__root__=[])
        for item in data.__root__:
            if item.noco_id in ids:
                filtered.__root__.append(item)
        return filtered


class ShowFormData(BaseModel):
    uuid: str
    name: str 


class ProducerUploadData(BaseModel):
    """Contains all information needed by the client in the upload form."""
    producer_name: str
    shows: Optional[list[ShowFormData]]

    @classmethod
    def from_nocodb(cls, producer_uuid: str):
        producer_data = get_nocodb_data(
            settings["project_name"],
            settings["producer_table"],
            filter_obj=EqFilter("UUID", producer_uuid),
        )
        if len(producer_data["list"]) != 1:
            raise KeyError("no producer found")
        producer = NocoProducer.parse_obj(producer_data["list"][0])
        show_ids = [show["Id"] for show in producer_data["list"][0][f"{settings['show_table']} List"]]
        shows_src = NocoShows.from_nocodb(ids=show_ids)
        shows = []
        print(shows_src)
        for show in shows_src.__root__:
            shows.append(ShowFormData(
                uuid=show.uuid,
                name=show.name,
            ))
        return cls(
            producer_name=f"{producer.first_name} {producer.last_name}",
            shows=shows,
        )
