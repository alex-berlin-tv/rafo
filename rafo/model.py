import enum

from .baserow import MultipleSelectEntry, MultipleSelectField, RowLink, Table, TableLinkField
from .config import settings
from .log import logger

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, List, Optional

from nocodb.nocodb import APIToken, NocoDBProject, WhereFilter
from nocodb.filters import EqFilter
from nocodb.infra.requests_client import NocoDBRequestsClient
from pydantic import BaseModel, Field, RootModel
from pydantic.config import ConfigDict
from pydantic.fields import computed_field


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
    logger.debug(
        f"NocoDB table_row_list for {project_name}/{table_name} with filter {filter_obj}")
    return client.table_row_list(
        get_nocodb_project(),
        table_name,
        filter_obj=filter_obj,
    )


class BaserowPerson(Table):
    """A person (formerly called Producer) in Baserow."""
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    email: str = Field(alias=str("E-Mail"))
    shows: TableLinkField = Field(alias=str("Format"))
    uuid: str = Field(alias=str("UUID"))

    table_id: ClassVar[int] = settings.br_person_table
    table_name: ClassVar[str] = "Person"
    model_config = ConfigDict(populate_by_name=True)

    def row_link(self) -> RowLink:
        """Returns RowLinkj to link this table using a TableLinkField."""
        return RowLink(
            row_id=self.row_id,
            key=None,
        )


class OldNocoProducer(BaseModel):
    """A Producer in NocoDB."""
    noco_id: int = Field(alias=str("Id"))
    created_at: datetime = Field(alias=str("CreatedAt"))
    updated_at: datetime = Field(alias=str("UpdatedAt"))
    first_name: str = Field(alias=str("Vorname"))
    last_name: str = Field(alias=str("Name"))
    ident: str = Field(alias=str("Ident"))
    email: str = Field(alias=str("Email"))
    uuid: str = Field(alias=str("UUID"))

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


class BaserowShow(Table):
    """
    A show (»Format«) has one or more producers and contains multiple episodes.
    """
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    responsible: Any = Field(alias=str("Verantwortlich"))
    uuid: str = Field(alias=str("UUID"))
    supervision: Any = Field(alias=str("Betreuung"))

    table_id: ClassVar[int] = settings.br_show_table
    table_name: ClassVar[str] = "Format"
    model_config = ConfigDict(populate_by_name=True)

    def row_link(self) -> RowLink:
        """Returns RowLink to link to this row using a TableLinkField."""
        return RowLink(
            row_id=self.row_id,
            key=None,
        )


class OldNocoShow(BaseModel):
    noco_id: int = Field(alias=str("Id"))
    created_at: datetime = Field(alias=str("CreatedAt"))
    updated_at: datetime = Field(alias=str("UpdatedAt"))
    name: str = Field(alias=str("Name"))
    ident: str = Field(alias=str("Ident"))
    uuid: str = Field(alias=str("UUID"))
    name: str = Field(alias=str("Name"))
    description: Optional[str] = Field(alias=str("Description"))

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


class NocoShows(RootModel[list[OldNocoShow]]):
    root: list[OldNocoShow]


class ShowFormData(BaseModel):
    uuid: str
    name: str

    @classmethod
    def from_noco_show(cls, show: OldNocoShow):
        return cls(
            uuid=show.uuid,
            name=show.name,
        )

    @classmethod
    def from_db_show(cls, show: BaserowShow):
        return cls(
            uuid=show.uuid,
            name=show.name,
        )


class ProducerUploadData(BaseModel):
    """Contains all information needed to display the upload form frontend."""
    producer_name: str
    shows: Optional[list[ShowFormData]]
    dev_mode: bool
    maintenance_mode: bool
    maintenance_message: str

    @classmethod
    def from_db(cls, person_uuid: str):
        person = BaserowPerson.by_uuid(person_uuid).one()
        shows = BaserowShow.by_link_field(person.shows).any()
        return cls(
            producer_name=person.name,
            shows=[ShowFormData.from_db_show(show) for show in shows],
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


class UploadState(str, Enum):
    """Indication of multiple long-running processes for upload entries."""
    WAVEFORM_PENDING = "Waveform: Ausstehend"
    WAVEFORM_RUNNING = "Waveform: Läuft"
    WAVEFORM_COMPLETE = "Waveform: Fertig"
    WAVEFORM_ERROR = "Waveform: Fehler"
    OPTIMIZATION_PENDING = "Optimierung: Ausstehend"
    OPTIMIZATION_RUNNING = "Optimierung: Läuft"
    OPTIMIZATION_COMPLETE = "Optimierung: Fertig"
    OPTIMIZATION_SEE_LOG = "Optimierung: Fertig, Log beachten!"
    OPTIMIZATION_ERROR = "Optimierung: Fehler"
    OMNIA_PENDING = "Omnia: Nicht auf Omnia"
    OMNIA_RUNNING = "Omnia: Upload läuft"
    OMNIA_COMPLETE = "Omnia: Liegt auf Omnia"
    OMNIA_ERROR = "Omnia: Fehler während Upload"


class UploadStates(RootModel[list[UploadState]]):
    """
    Handles the replacement of a single status within the Multi Select Field.
    """
    root: list[UploadState]

    WAVEFORM_PREFIX: ClassVar[str] = "Waveform"
    OPTIMIZATION_PREFIX: ClassVar[str] = "Optimierung"
    OMNIA_PREFIX: ClassVar[str] = "Omnia"
    ORDER: ClassVar[list[str]] = [
        WAVEFORM_PREFIX, OPTIMIZATION_PREFIX, OMNIA_PREFIX
    ]

    @classmethod
    def from_multiple_select_field(cls, field: MultipleSelectField) -> "UploadStates":
        """Parses a Baserow multiple select field model."""
        entries = []
        for field_entry in field.root:
            for enum_entry in UploadState:
                if field_entry.value == enum_entry.value:
                    entries.append(enum_entry)
        rsl = cls(root=entries)
        rsl.sort()
        return rsl

    @classmethod
    def all_pending(cls) -> "UploadStates":
        """Returns all states to be pending."""
        return cls(root=[
            UploadState.WAVEFORM_PENDING,
            UploadState.OPTIMIZATION_PENDING,
            UploadState.OMNIA_PENDING,
        ])

    def values(self) -> list[str]:
        """Returns all values as list of strings."""
        return [entry.value for entry in self.root]

    def update_state(self, prefix: str, new_state: UploadState):
        """Replaces the state with the given prefix."""
        keep = [
            state for state in self.root if not state.value.startswith(prefix)
        ]
        self.root = [new_state] + keep

    def sort(self):
        """Ensures that the statuses are always sorted in the same order."""
        def sort_by_order(value):
            for index, prefix in enumerate(self.ORDER):
                if value.startswith(prefix):
                    return (index, value)
            return (-1, value)
        self.root = sorted(self.root, key=sort_by_order)

    def to_multiple_select_field(self) -> MultipleSelectField:
        """Converts the state collection to a MultipleSelectField."""
        rsl: list[MultipleSelectEntry] = []
        for entry in self.root:
            rsl.append(MultipleSelectEntry(id=None, value=entry, color=None))
        return MultipleSelectField(rsl)


class BaserowUpload(Table):
    """A upload of an episode for a show by a person."""
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    uploader: TableLinkField = Field(alias=str("Eingereicht von"))
    show: TableLinkField = Field(alias=str("Format"))
    planned_broadcast_at: datetime = Field(
        alias=str("Geplante Ausstrahlung"))
    description: Optional[str] = Field(alias=str("Beschreibung"), default=None)
    comment_producer: Optional[str] = Field(
        alias=str("Kommentar Produzent"), default=None
    )
    source_file: Optional[Any] = Field(alias=str("Quelldatei"), default=None)
    optimized_file: Optional[Any] = Field(
        alias=str("Optimierte Datei"), default=None
    )
    manual_file: Optional[Any] = Field(
        alias=str("Manuelle Datei"), default=None
    )
    cover: Optional[Any] = Field(alias=str("Cover"), default=None)
    waveform: Optional[Any] = Field(alias=str("Waveform"), default=None)
    state: MultipleSelectField = Field(
        alias=str("Status"),
        default=UploadStates.all_pending().to_multiple_select_field(),
    )
    optimization_log: Optional[str] = Field(
        alias=str("Log Optimierung"), default=None
    )
    created_at: Optional[datetime] = Field(
        alias=str("Hochgeladen am"), default=None
    )
    table_id: ClassVar[int] = settings.br_upload_table
    table_name: ClassVar[str] = "Upload"
    model_config = ConfigDict(populate_by_name=True)
    dump_payload = True

    @computed_field
    @property
    def state_enum(self) -> UploadStates:
        return UploadStates.from_multiple_select_field(self.state)

    def get_uploader(self) -> BaserowPerson:
        """Get DB entry of the person which did the upload."""
        return BaserowPerson.by_link_field(self.uploader).one()

    def get_show(self) -> BaserowShow:
        """Get DB entry of the show linked to the upload."""
        return BaserowShow.by_link_field(self.show).one()

    def update_state(self, prefix: str, new_state: UploadState):
        """Update the the state with the given prefix."""
        enum = self.state_enum
        enum.update_state(prefix, new_state)
        self.update(self.row_id, state=enum.to_multiple_select_field())

    def update_optimizing_log(self, value: str):
        """Updates the optimization log field."""
        self.update(self.row_id, optimization_log=value)

    def file_name_prefix(self) -> str:
        """Canonical filename for a given Episode."""
        date = self.planned_broadcast_at.strftime("%y%m%d-%H%M")
        return f"{date}_{self.row_id}"
        # show = normalize_for_filename(self.get_show().name)
        # return f"e-{self.noco_id:05d}_{date}_{show}"


class NocoEpisode(BaseModel):
    noco_id: int = Field(alias=str("Id"))
    created_at: Optional[datetime] = Field(
        alias=str("CreatedAt"), default=None)
    updated_at: Optional[datetime] = Field(
        alias=str("UpdatedAt"), default=None)
    title: str = Field(alias=str("Titel"))
    description: str = Field(alias=str("Beschreibung"))
    comment_producer: Optional[str] = Field(alias=str("Kommentar Produzent"))
    source_file: Optional[Any] = Field(alias=str("Quelldatei"))
    optimized_file: Optional[Any] = Field(alias=str("Optimierte Datei"))
    manual_file: Optional[Any] = Field(alias=str("Manuelle Datei"))
    waveform: Optional[Any] = Field(alias=str("Waveform"))
    uuid: str = Field(alias=str("UUID"))
    planned_broadcast_at: datetime = Field(alias=str("Geplante Ausstrahlung"))
    state_omnia: Optional[str] = Field(alias=str("Status Omnia"))
    state_waveform: Optional[WaveformState] = Field(
        alias=str("Status Waveform"))
    state_optimizing: Optional[OptimizingState] = Field(
        alias=str("Status Optimierung")
    )

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

    def get_producer(self) -> "OldNocoProducer":
        client = get_nocodb_client()
        logger.debug(
            f"NocoDB table_row_nested_relations_list for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        raw = client.table_row_nested_relations_list(
            get_nocodb_project(),
            settings.episode_table,
            "mm",
            self.noco_id,
            settings.producer_column,
        )
        if len(raw["list"]) < 1:
            raise ValueError(
                f"no producer linked in episode with id {self.noco_id}")
        elif len(raw["list"]) > 1:
            raise ValueError(
                f"more than one producer linked in episode with id {self.noco_id}")
        return OldNocoProducer.model_validate(raw["list"][0])

    def get_show(self) -> "OldNocoShow":
        client = get_nocodb_client()
        logger.debug(
            f"NocoDB table_row_nested_relations_list for {settings.project_name}/{settings.episode_table} for Field '{settings.show_column}'")
        raw = client.table_row_nested_relations_list(
            get_nocodb_project(),
            settings.episode_table,
            "mm",
            self.noco_id,
            settings.show_column,
        )
        if len(raw["list"]) < 1:
            raise ValueError(
                f"no show linked in episode with id {self.noco_id}")
        elif len(raw["list"]) > 1:
            raise ValueError(
                f"more than one show linked in episode with id {self.noco_id}")
        return OldNocoShow.model_validate(raw["list"][0])

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
    title: str = Field(alias=str("Titel"))
    uuid: str = Field(alias=str("UUID"))
    description: str = Field(alias=str("Beschreibung"))
    planned_broadcast_at: str = Field(alias=str("Geplante Ausstrahlung"))
    comment: str = Field(alias=str("Kommentar Produzent"))
    state_waveform: Optional[WaveformState] = Field(
        alias=str("Status Waveform"), default=WaveformState.PENDING)
    state_optimizing: Optional[OptimizingState] = Field(
        alias=str("Status Optimierung"), default=OptimizingState.PENDING)

    class Config:
        populate_by_name = True

    def add_to_noco(self, producer_uuid: str, show_uuid: str):
        """Adds the entry to NocoDB using the API."""
        client = get_nocodb_client()
        project = get_nocodb_project()
        logger.debug(
            f"NocoDB table_row_create for {settings.project_name}/{settings.episode_table}")
        episode_data = client.table_row_create(
            project,
            settings.episode_table,
            self.model_dump(by_alias=True)
        )
        episode = NocoEpisode.model_validate(episode_data)
        producer = OldNocoProducer.from_nocodb_by_uuid(producer_uuid)
        show = OldNocoShow.from_nocodb_by_uuid(show_uuid)
        logger.debug(
            f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.show_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table,
            "mm",
            episode.noco_id,
            settings.show_column,
            show.noco_id,
        )
        logger.debug(
            f"NocoDB table_row_relation_create for {settings.project_name}/{settings.episode_table} for Field '{settings.producer_column}'")
        client.table_row_relation_create(
            project,
            settings.episode_table,
            "mm",
            episode.noco_id,
            settings.producer_column,
            producer.noco_id,
        )
        return episode.noco_id
