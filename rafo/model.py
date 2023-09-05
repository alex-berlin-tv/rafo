from .config import settings
from .log import logger
from .utils import normalize_for_filename

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from nocodb.nocodb import APIToken, NocoDBProject, WhereFilter
from nocodb.filters import EqFilter
from nocodb.infra.requests_client import NocoDBRequestsClient
from pydantic import BaseModel, Field, RootModel


def get_nocodb_client() -> NocoDBRequestsClient:
    """Returns the client instance based on the values in the setting file."""
    token = settings.nocodb_api_key
    if not isinstance(token, str):
        raise ValueError("invalid nocodb token, not a string")
    return NocoDBRequestsClient(
        APIToken(token), 
        settings.nocodb_url,
    )


def get_nocodb_project() -> NocoDBProject:
    """
    Returns the project instance for the NocoDB Library based on the values in the
    setting file.
    """
    return NocoDBProject("noco", settings.project_name)


def get_nocodb_data(project_name: str, table_name: str, filter_obj: Optional[WhereFilter] = None) -> Any:
    """Get all items of a specified table from the configured NocoDB instance and project."""
    client = get_nocodb_client()
    logger.debug(f"NocoDB table_row_list for {project_name}/{table_name} with filter {filter_obj}")
    return client.table_row_list(
        get_nocodb_project(),
        table_name,
        filter_obj=filter_obj,
    )


class NocoProducer(BaseModel):
    """A Producer in NocoDB."""
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
        """Get an Producer from NocoDB by a given UUID."""
        raw = get_nocodb_data(
            settings.project_name, 
            settings.producer_table, 
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
            settings.project_name,
            settings.show_table,
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no show for UUID {uuid} found")
        return cls.model_validate(raw["list"][0])


class NocoShows(RootModel[list[NocoShow]]):
    root: list[NocoShow]


class ShowFormData(BaseModel):
    uuid: str
    name: str

    @classmethod
    def from_noco_show(cls, show: NocoShow):
        return cls(
            uuid=show.uuid,
            name=show.name,
        )


class ProducerUploadData(BaseModel):
    """Contains all information needed by the client in the upload form."""
    producer_name: str
    shows: Optional[list[ShowFormData]]
    dev_mode: bool
    maintenance_mode: bool
    maintenance_message: str

    @classmethod
    def from_nocodb(cls, producer_uuid: str):
        producer_data = get_nocodb_data(
            settings.project_name,
            settings.producer_table,
            filter_obj=EqFilter("UUID", producer_uuid),
        )
        if len(producer_data["list"]) != 1:
            raise KeyError("no producer found")
        producer = NocoProducer.model_validate(producer_data["list"][0])
        shows_raw = get_nocodb_client().table_row_nested_relations_list(
            get_nocodb_project(),
            settings.producer_table,
            "mm",
            producer.noco_id,
            settings.show_table,
        )
        shows = NocoShows.model_validate(shows_raw["list"])
        return cls(
            producer_name=f"{producer.first_name} {producer.last_name}",
            shows=[ShowFormData.from_noco_show(show) for show in shows.root],
            dev_mode=settings.dev_mode,
            maintenance_mode=settings.maintenance_mode,
            maintenance_message=settings.maintenance_message,
        )


class WaveformState(str, Enum):
    PENDING = "Ausstehend"
    RUNNING = "Läuft"
    DONE = "Fertig"
    ERROR = "Fehler"


class OptimizingState(str, Enum):
    PENDING = "Ausstehend"
    RUNNING = "Läuft"
    DONE = "Fertig"
    SEE_LOG = "Fertig – Siehe Log"
    ERROR = "Fehler"


class OmniaState(str, Enum):
    MISSING = "Nicht auf Omnia"
    CMD_START_UPLOAD = "STARTE Upload zu Omnia"
    AVAILABLE = "Liegt auf Omnia bereit "
    CMD_PUBLISH = "VERÖFFENTLICHEN"
    ONLINE = "Online in der Mediathek"
    CMD_DEACTIVATE = "DEPUBLIZIEREN"


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
    state_waveform: Optional[WaveformState] = Field(alias="Status Waveform")
    state_optimizing: Optional[OptimizingState] = Field(alias="Status Optimierung")

    @classmethod
    def from_nocodb_by_id(cls, id: int):
        raw = get_nocodb_data(
            settings.project_name, 
            settings.episode_table, 
            filter_obj=EqFilter("Id", str(id)),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no episode for Id {id} found")
        return cls.model_validate(raw["list"][0])

    @classmethod
    def from_nocodb_by_uuid(cls, uuid: str):
        raw = get_nocodb_data(
            settings.project_name, 
            settings.episode_table, 
            filter_obj=EqFilter("UUID", uuid),
        )
        if len(raw["list"]) != 1:
            raise KeyError(f"no episode for UUID {uuid} found")
        return cls.model_validate(raw["list"][0])

    def get_producer(self) -> "NocoProducer":
        client = get_nocodb_client()
        logger.debug(f"NocoDB table_row_nested_relations_list for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        raw = client.table_row_nested_relations_list(
            get_nocodb_project(),
            settings.episode_table,
            "mm",
            self.noco_id,
            settings.producer_column,
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
            get_nocodb_project(),
            settings.episode_table,
            "mm",
            self.noco_id,
            settings.show_column,
        )
        if len(raw["list"]) < 1:
            raise ValueError(f"no show linked in episode with id {self.noco_id}")
        elif len(raw["list"]) > 1:
            raise ValueError(f"more than one show linked in episode with id {self.noco_id}")
        return NocoShow.model_validate(raw["list"][0])

    def update_state_waveform(self, state: WaveformState):
        """Updates the state indicator for the waveform worker."""
        get_nocodb_client().table_row_update(
            get_nocodb_project(),
            settings.episode_table,
            self.noco_id,
            {"Status Waveform": state.value},
        )
    
    def update_state_optimizing(self, state: OptimizingState):
        """Updates the state indicator for the optimizing worker."""
        get_nocodb_client().table_row_update(
            get_nocodb_project(),
            settings.episode_table,
            self.noco_id,
            {"Status Optimierung": state.value},
        )
    
    def update_state_omnia(self, state: OmniaState):
        """Updates the Omnia upload state."""
        get_nocodb_client().table_row_update(
            get_nocodb_project(),
            settings.episode_table,
            self.noco_id,
            {"Status Omnia": state.value},
        )

    def update_optimizing_log(self, log: str):
        """Updates the content of the optimizing log field."""
        get_nocodb_client().table_row_update(
            get_nocodb_project(),
            settings.episode_table,
            self.noco_id,
            {"Log Optimierung": log}
        )

    def file_name_prefix(self) -> str:
        """Canonical filename for a given Episode."""
        return self.planned_broadcast_at.strftime("%y%m%d-%H%M")
        # show = normalize_for_filename(self.get_show().name)
        # return f"e-{self.noco_id:05d}_{date}_{show}"


class NocoEpisodeNew(BaseModel):
    """A new Episode entry which should be added to NocoDB."""
    title: str = Field(alias="Titel")
    uuid: str = Field(alias="UUID")
    description: str = Field(alias="Beschreibung")
    planned_broadcast_at: str = Field(alias="Geplante Ausstrahlung")
    comment: str = Field(alias="Kommentar Produzent")
    state_waveform: Optional[WaveformState] = Field(alias="Status Waveform", default=WaveformState.PENDING)
    state_optimizing: Optional[OptimizingState] = Field(alias="Status Optimierung", default=OptimizingState.PENDING)

    class Config:
        populate_by_name = True

    def add_to_noco(self, producer_uuid: str, show_uuid: str):
        """Adds the entry to NocoDB using the API."""
        client = get_nocodb_client()
        project = get_nocodb_project()
        logger.debug(f"NocoDB table_row_create for {settings.project_name}/{settings.episode_table}")
        episode_data = client.table_row_create(
            project,
            settings.episode_table,
            self.model_dump(by_alias=True)
        )
        episode = NocoEpisode.model_validate(episode_data)
        producer = NocoProducer.from_nocodb_by_uuid(producer_uuid)
        show = NocoShow.from_nocodb_by_uuid(show_uuid)
        logger.debug(f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.show_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table,
            "mm",
            episode.noco_id,
            settings.show_column,
            show.noco_id,
        )
        logger.debug(f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table,
            "mm",
            episode.noco_id,
            settings.producer_column,
            producer.noco_id,
        )
        return episode.noco_id
    
