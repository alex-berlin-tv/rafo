from config import settings

from typing import Any, Optional
from datetime import datetime

from nocodb.nocodb import APIToken, NocoDBProject, WhereFilter
from nocodb.filters import EqFilter
from nocodb.infra.requests_client import NocoDBRequestsClient
from pydantic import BaseModel, Field


def get_nocodb_client() -> NocoDBRequestsClient:
    token = settings["nocodb_api_key"]
    if not isinstance(token, str):
        raise ValueError("invalid nocodb token, not a string")
    return NocoDBRequestsClient(
        APIToken(token),  # type: ignore
        settings["nocodb_url"],
    )


def get_nocodb_project(project_name) -> NocoDBProject:
    return NocoDBProject("noco", project_name)


def get_nocodb_data(project_name: str, table_name: str, filter_obj: Optional[WhereFilter] = None) -> Any:
    client = get_nocodb_client()
    return client.table_row_list(
        get_nocodb_project(project_name),
        table_name,
        filter_obj=filter_obj,
    )


class NocoEpisode(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: Optional[datetime] = Field(alias="CreatedAt")
    updated_at: Optional[datetime] = Field(alias="UpdatedAt")
    title: str = Field(alias="Titel")
    description: str = Field(alias="Beschreibung")
    comment_producer: Optional[str] = Field(alias="Kommentar Produzent")
    source_file: Optional[str] = Field(alias="Quelldatei")
    optimized_file: Optional[str] = Field(alias="Optimierte Datei")
    manual_file: Optional[str] = Field(alias="Manuelle Datei")
    waveform: Optional[str] = Field(alias="Waveform")
    uuid: str = Field(alias="UUID")
    planned_broadcast_at: datetime = Field(alias="Geplante Ausstrahlung")
    state_omnia: Optional[str] = Field(alias="Status Omnia")
    state_waveform: Optional[str] = Field(alias="Status Waveform")
    state_optimizing: Optional[str] = Field(alias="Status Optimierung")


class NocoEpisodeNew(BaseModel):
    title: str = Field(alias="Titel")
    uuid: str = Field(alias="UUID")
    description: str = Field(alias="Beschreibung")
    planned_broadcast_at: str = Field(alias="Geplante Ausstrahlung")
    comment: str = Field(alias="Kommentar Produzent")

    class Config:
        allow_population_by_field_name = True

    def add_to_noco(self, producer_uuid: str, show_uuid: str):
        client = get_nocodb_client()
        project = get_nocodb_project(settings["project_name"])
        episode_data = client.table_row_create(
            project,
            settings.episode_table,  # type: ignore
            self.dict(by_alias=True)
        )
        episode = NocoEpisode.parse_obj(episode_data)
        producer = NocoProducer.from_nocodb_by_uuid(producer_uuid)
        show = NocoShow.from_nocodb_by_uuid(show_uuid)
        client.table_row_relation_create(
            project,
            settings.episode_table,  # type: ignore
            relation_type="mm",
            row_id=episode.noco_id,
            column_name="Format",
            ref_row_id=show.noco_id,
        )
        client.table_row_relation_create(
            project,
            settings.episode_table,  # type: ignore
            relation_type="mm",
            row_id=episode.noco_id,
            column_name="Eingereicht von",
            ref_row_id=producer.noco_id,
        )
        return episode.noco_id


class NocoProducer(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    first_name: str = Field(alias="Vorname")
    last_name: str = Field(alias="Name")
    ident: str = Field(alias="Ident")
    email: str = Field(alias="Email")
    uuid: str = Field(alias="UUID")

    @classmethod
    def from_nocodb_by_uuid(cls, uuid: str):
        raw = get_nocodb_data(
            settings.project_name,  # type: ignore
            settings.producer_table,  # type: ignore
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no producer for UUID {uuid} found")
        return cls.parse_obj(raw["list"][0])


class NocoShow(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    ident: str = Field(alias="Ident")
    uuid: str = Field(alias="UUID")
    name: str = Field(alias="Name")
    description: Optional[str] = Field(alias="Description")

    @classmethod
    def from_nocodb_by_uuid(cls, uuid: str):
        raw = get_nocodb_data(
            settings.project_name,  # type: ignore
            settings.show_table,  # type: ignore
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no show for UUID {uuid} found")
        return cls.parse_obj(raw["list"][0])


class NocoShows(BaseModel):
    __root__: list[NocoShow]

    @classmethod
    def from_nocodb(cls, ids: Optional[list[int]] = None):
        if ids is None:
            raise NotImplementedError(
                "getting shows without id is not implemented sorry")
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
        show_ids = [show["Id"] for show in producer_data["list"]
                    [0][f"{settings['show_table']} List"]]
        shows_src = NocoShows.from_nocodb(ids=show_ids)
        shows = []
        for show in shows_src.__root__:
            shows.append(ShowFormData(
                uuid=show.uuid,
                name=show.name,
            ))
        return cls(
            producer_name=f"{producer.first_name} {producer.last_name}",
            shows=shows,
        )
