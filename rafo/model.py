from .config import settings
from .log import logger

from datetime import datetime
from typing import Any, Optional

from nocodb.nocodb import APIToken, NocoDBProject, WhereFilter
from nocodb.filters import EqFilter
from nocodb.infra.requests_client import NocoDBRequestsClient
from pydantic import BaseModel, Field, RootModel

def get_nocodb_client() -> NocoDBRequestsClient:
    token = settings["nocodb_api_key"]
    if not isinstance(token, str):
        raise ValueError("invalid nocodb token, not a string")
    return NocoDBRequestsClient(
        APIToken(token),  # type: ignore
        settings["nocodb_url"],
    )


def get_nocodb_project(project_name: str) -> NocoDBProject:
    return NocoDBProject("noco", project_name)


def get_nocodb_data(project_name: str, table_name: str, filter_obj: Optional[WhereFilter] = None) -> Any:
    client = get_nocodb_client()
    logger.debug(f"NocoDB table_row_list for {project_name}/{table_name} with filter {filter_obj}")
    return client.table_row_list(
        get_nocodb_project(project_name),
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

    @classmethod
    def from_nocodb_by_uuid(cls, uuid: str):
        raw = get_nocodb_data(
            settings.project_name,  # type: ignore
            settings.producer_table,  # type: ignore
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no producer for UUID {uuid} found")
        return cls.model_validate(raw["list"][0])


class NocoShow(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    name: str = Field(alias="Name")
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
        return cls.model_validate(raw["list"][0])


class NocoShows(RootModel[list[NocoShow]]):
    root: list[NocoShow]

    @classmethod
    def from_nocodb(cls, ids: Optional[list[int]] = None):
        if ids is None:
            raise NotImplementedError(
                "getting shows without id is not implemented sorry")
        raw = get_nocodb_data(
            settings["project_name"],
            settings["show_table"],
        )
        data = cls.model_validate(raw["list"])
        filtered = NocoShows(root=[])
        for item in data.root:
            if item.noco_id in ids:
                filtered.root.append(item)
        return filtered


class ShowFormData(BaseModel):
    uuid: str
    name: str


class ProducerUploadData(BaseModel):
    """Contains all information needed by the client in the upload form."""
    producer_name: str
    shows: Optional[list[ShowFormData]]
    dev_mode: bool

    @classmethod
    def from_nocodb(cls, producer_uuid: str):
        producer_data = get_nocodb_data(
            settings["project_name"],
            settings["producer_table"],
            filter_obj=EqFilter("UUID", producer_uuid),
        )
        if len(producer_data["list"]) != 1:
            raise KeyError("no producer found")
        producer = NocoProducer.model_validate(producer_data["list"][0])
        show_ids = [show["Id"] for show in producer_data["list"]
                    [0][f"{settings['show_table']} List"]]
        shows_src = NocoShows.from_nocodb(ids=show_ids)
        shows = []
        for show in shows_src.root:
            shows.append(ShowFormData(
                uuid=show.uuid,
                name=show.name,
            ))
        return cls(
            producer_name=f"{producer.first_name} {producer.last_name}",
            shows=shows,
            dev_mode=settings.dev_mode, # type: ignore
        )


class NocoEpisode(BaseModel):
    noco_id: int = Field(alias="Id")
    created_at: Optional[datetime] = Field(alias="CreatedAt", default=None)
    updated_at: Optional[datetime] = Field(alias="UpdatedAt", default=None)
    title: str = Field(alias="Titel")
    description: str = Field(alias="Beschreibung")
    comment_producer: Optional[str] = Field(alias="Kommentar Produzent")
    source_file: Optional[Any] = Field(alias="Quelldatei")
    optimized_file: Optional[Any] = Field(alias="Optimierte Datei")
    manual_file: Optional[Any] = Field(alias="Manuelle Datei")
    waveform: Optional[Any] = Field(alias="Waveform")
    uuid: str = Field(alias="UUID")
    planned_broadcast_at: datetime = Field(alias="Geplante Ausstrahlung")
    state_omnia: Optional[str] = Field(alias="Status Omnia")
    state_waveform: Optional[str] = Field(alias="Status Waveform")
    state_optimizing: Optional[str] = Field(alias="Status Optimierung")

    @classmethod
    def from_nocodb_by_id(cls, id: int):
        raw = get_nocodb_data(
            settings.project_name,  # type: ignore
            settings.episode_table,  # type: ignore
            filter_obj=EqFilter("Id", str(id)),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no episode for Id {id} found")
        return cls.model_validate(raw["list"][0])

    @classmethod
    def from_nocodb_by_uuid(cls, uuid: str):
        raw = get_nocodb_data(
            settings.project_name,  # type: ignore
            settings.episode_table,  # type: ignore
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no episode for UUID {uuid} found")
        return cls.model_validate(raw["list"][0])

    def get_producer(self) -> "NocoProducer":
        client = get_nocodb_client()
        logger.debug(f"NocoDB table_row_nested_relations_list for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        raw = client.table_row_nested_relations_list(
            get_nocodb_project(settings.project_name), # type: ignore
            settings.episode_table, # type: ignore
            "mm",
            self.noco_id,
            settings.producer_column, # type: ignore
        )
        if len(raw["list"]) < 1:
            raise ValueError(f"no producer linked in episode with id {self.noco_id}")
        elif len(raw["list"]) > 1:
            raise ValueError(f"more than one producer linked in episode with id {self.noco_id}")
        return NocoProducer.model_validate(raw["list"][0])
    
    def get_show(self) -> "NocoShow":
        client = get_nocodb_client()
        logger.debug(f"NocoDB table_row_nested_relations_list for {settings.project_name}/{settings.episode_table} for Field '{settings.show_column}'")
        raw = client.table_row_nested_relations_list(
            get_nocodb_project(settings.project_name), # type: ignore
            settings.episode_table, # type: ignore
            "mm",
            self.noco_id,
            settings.show_column, # type: ignore
        )
        if len(raw["list"]) < 1:
            raise ValueError(f"no show linked in episode with id {self.noco_id}")
        elif len(raw["list"]) > 1:
            raise ValueError(f"more than one show linked in episode with id {self.noco_id}")
        return NocoShow.model_validate(raw["list"][0])


class NocoEpisodeNew(BaseModel):
    title: str = Field(alias="Titel")
    uuid: str = Field(alias="UUID")
    description: str = Field(alias="Beschreibung")
    planned_broadcast_at: str = Field(alias="Geplante Ausstrahlung")
    comment: str = Field(alias="Kommentar Produzent")

    class Config:
        populate_by_name = True

    def add_to_noco(self, producer_uuid: str, show_uuid: str):
        client = get_nocodb_client()
        project = get_nocodb_project(settings.project_name) # type: ignore
        logger.debug(f"NocoDB table_row_create for {settings.project_name}/{settings.episode_table}")
        episode_data = client.table_row_create(
            project,
            settings.episode_table,  # type: ignore
            self.dict(by_alias=True)
        )
        episode = NocoEpisode.model_validate(episode_data)
        producer = NocoProducer.from_nocodb_by_uuid(producer_uuid)
        show = NocoShow.from_nocodb_by_uuid(show_uuid)
        logger.debug(f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.show_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table, # type: ignore
            "mm",
            episode.noco_id,
            settings.show_column, # type: ignore
            show.noco_id,
        )
        logger.debug(f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table, # type: ignore
            "mm",
            episode.noco_id,
            settings.producer_column, # type: ignore
            producer.noco_id,
        )
        return episode.noco_id

