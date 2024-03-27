from .baserow import DurationField, FileField, MultipleSelectField, NoResultError, RowLink, SelectEntry, Table, TableLinkField
from .config import settings

from datetime import datetime, timedelta
from enum import Enum
from typing import ClassVar, Optional
from urllib.parse import urljoin

from pydantic import BaseModel, Field, RootModel
from pydantic.config import ConfigDict
from pydantic.fields import PrivateAttr, computed_field


class BaserowPerson(Table):
    """A person (formerly called Producer) in Baserow."""
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    email: str = Field(alias=str("E-Mail"))
    shows: TableLinkField = Field(alias=str("Format"))
    uuid: str = Field(alias=str("UUID"))
    upload_form_state: SingleSelectField = Field(
        alias=str("Status Upload Form")
    )
    legacy_uuid: Optional[str] = Field(alias=str("Legacy UUID"), default=None)

    table_id: ClassVar[int] = settings.person_table
    table_name: ClassVar[str] = "Person"
    model_config = ConfigDict(populate_by_name=True)

    def row_link(self) -> RowLink:
        """Returns RowLink to link this table using a TableLinkField."""
        return RowLink(
            row_id=self.row_id,
            key=None,
        )

    def is_form_enabled(self) -> bool:
        """Returns whether the upload form is enabled for this person."""
        return self.upload_form_state is not None and self.upload_form_state.value == "Aktiviert"

    def upload_url(self) -> str:
        """Returns the URL of the personalized upload form for this person."""
        return urljoin(settings.base_url, f"upload/{self.uuid}")


class BaserowShow(Table):
    """
    A show (»Format«) has one or more producers and contains multiple episodes.
    """
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    responsible: TableLinkField = Field(alias=str("Verantwortlich"))
    medium: SingleSelectField = Field(alias=str("Medium"))
    description: str = Field(alias=str("Beschreibung"))
    supervisors: TableLinkField = Field(alias=str("Betreuung"))
    cover: Optional[FileField] = Field(
        alias=str("Cover"), default=None
    )
    omnia_id: Optional[int] = Field(alias=str("Omnia ID"), default=None)

    table_id: ClassVar[int] = settings.show_table
    table_name: ClassVar[str] = "Format"
    model_config = ConfigDict(populate_by_name=True)

    def row_link(self) -> RowLink:
        """Returns RowLink to link to this row using a TableLinkField."""
        return RowLink(
            row_id=self.row_id,
            key=None,
        )

    def is_radio(self) -> bool:
        """Returns whether the medium of the given show is Radio."""
        if self.medium is None:
            return False
        return "Radio" == self.medium.value


class ShowFormData(BaseModel):
    show_id: int
    name: str

    @classmethod
    def from_db_show(cls, show: BaserowShow):
        return cls(
            show_id=show.row_id,
            name=show.name,
        )


class ProducerUploadData(BaseModel):
    """Contains all information needed to display the upload form frontend."""
    producer_name: str
    producer_uuid: str
    base_url: str
    shows: Optional[list[ShowFormData]]
    dev_mode: bool
    maintenance_mode: bool
    maintenance_message: str
    form_enabled: bool
    legacy_url_used: bool
    legacy_url_grace_date: Optional[datetime]

    @classmethod
    async def from_db(cls, person_uuid: str):
        legacy_url_used = False
        try:
            person_rsl = await BaserowPerson.by_uuid(person_uuid)
            person = person_rsl.one()
        except NoResultError:
            person_rsl = await BaserowPerson.filter(legacy_uuid=person_uuid)
            person = person_rsl.one()
            legacy_url_used = True
        shows_rsl = await BaserowShow.by_link_field(person.shows)
        shows = shows_rsl.any()
        return cls(
            producer_name=person.name,
            producer_uuid=person.uuid,
            base_url=settings.base_url,
            shows=[ShowFormData.from_db_show(show) for show in shows],
            dev_mode=settings.dev_mode,
            maintenance_mode=settings.maintenance_mode,
            maintenance_message=settings.maintenance_message,
            form_enabled=person.is_form_enabled(),
            legacy_url_used=legacy_url_used,
            legacy_url_grace_date=settings.legacy_url_grace_date,
        )


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
    INTERNAL_LEGACY_URL_USED = "Intern: Legacy URL benutzt"
    INTERNAL_NOCODB_IMPORT = "Intern: NocoDB Import"


class UploadStates(RootModel[list[UploadState]]):
    """
    Handles the replacement of a single status within the Multi Select Field.
    """
    root: list[UploadState]

    WAVEFORM_PREFIX: ClassVar[str] = "Waveform"
    OPTIMIZATION_PREFIX: ClassVar[str] = "Optimierung"
    OMNIA_PREFIX: ClassVar[str] = "Omnia"
    INTERNAL_PREFIX: ClassVar[str] = "URL"
    ORDER: ClassVar[list[str]] = [
        WAVEFORM_PREFIX, OPTIMIZATION_PREFIX, OMNIA_PREFIX, INTERNAL_PREFIX,
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
    def all_pending_with_legacy_url_state(cls, legacy_url_used: bool) -> "UploadStates":
        """
        Returns all states to be pending. When a legacy URL is used the
        appropriate state will be added as well.
        """
        rsl = [
            UploadState.WAVEFORM_PENDING,
            UploadState.OPTIMIZATION_PENDING,
            UploadState.OMNIA_PENDING,
        ]
        if legacy_url_used:
            rsl.append(UploadState.INTERNAL_LEGACY_URL_USED)
        return cls(root=rsl)

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
        rsl: list[SelectEntry] = []
        for entry in self.root:
            rsl.append(SelectEntry(id=None, value=entry, color=None))
        return MultipleSelectField(rsl)


class BaserowUpload(Table):
    """A upload of an episode for a show by a person."""
    row_id: int = Field(alias=str("id"))
    name: str = Field(alias=str("Name"))
    uploader: TableLinkField = Field(alias=str("Eingereicht von"))
    show: TableLinkField = Field(alias=str("Format"))
    planned_broadcast_at: datetime = Field(
        alias=str("Geplante Ausstrahlung"))
    description: Optional[str] = Field(
        alias=str("Beschreibung"), default=None
    )
    comment_producer: Optional[str] = Field(
        alias=str("Kommentar Produzent"), default=None
    )
    waveform: Optional[FileField] = Field(
        alias=str("Waveform"), default=None
    )
    source_file: Optional[FileField] = Field(
        alias=str("Quelldatei"), default=None
    )
    optimized_file: Optional[FileField] = Field(
        alias=str("Optimierte Datei"), default=None
    )
    manual_file: Optional[FileField] = Field(
        alias=str("Manuelle Datei"), default=None
    )
    cover: Optional[FileField] = Field(
        alias=str("Cover"), default=None
    )
    duration: Optional[DurationField] = Field(
        alias=str("Dauer"), default=None
    )
    state: MultipleSelectField = Field(
        alias=str("Status"),
        default=UploadStates.all_pending_with_legacy_url_state(
            False).to_multiple_select_field(),
    )
    optimization_log: Optional[str] = Field(
        alias=str("Log Optimierung"), default=None
    )
    created_at: Optional[datetime] = Field(
        alias=str("Hochgeladen am"), default=None
    )
    legacy_uuid: Optional[str] = Field(
        alias=str("Legacy UUID"), default=None,
    )
    omnia_id: Optional[int] = Field(
        alias=str("Omnia ID"), default=None,
    )
    table_id: ClassVar[int] = settings.upload_table
    table_name: ClassVar[str] = "Upload"
    model_config = ConfigDict(populate_by_name=True)

    _uploader_cache: Optional[BaserowPerson] = PrivateAttr(default=None)
    _show_cache: Optional[BaserowShow] = PrivateAttr(default=None)

    @computed_field
    @property
    def state_enum(self) -> UploadStates:
        return UploadStates.from_multiple_select_field(self.state)

    @property
    async def cached_uploader(self) -> BaserowPerson:
        """
        The linked person who uploaded the entry. Is always expected to be one
        entry. This data is therefore only cached on the first request that the
        linked entry is actually loaded by Baserow.
        """
        if self._uploader_cache is None:
            rsl = await BaserowPerson.by_link_field(
                self.uploader,
            )
            self._uploader_cache = rsl.one()
        return self._uploader_cache

    @property
    async def cached_show(self) -> BaserowShow:
        """
        The linked show for this entry. Is always expected to be one entry. This
        data is therefore only cached on the first request that the linked entry
        is actually loaded by Baserow.
        """
        if self._show_cache is None:
            rsl = await BaserowShow.by_link_field(self.show)
            self.__show_cache = rsl.one()
        return self.__show_cache

    async def update_state(self, prefix: str, new_state: UploadState):
        """Update the the state with the given prefix."""
        rsl = await BaserowUpload.by_id(self.row_id)
        current_db_entry = rsl.one()
        enum = current_db_entry.state_enum
        enum.update_state(prefix, new_state)
        self.update(self.row_id, state=enum.to_multiple_select_field())

    def file_name_prefix(self) -> str:
        """Canonical filename for a given Episode."""
        date = self.planned_broadcast_at.strftime("%y%m%d-%H%M")
        return f"{date}_{self.row_id}"
        # show = normalize_for_filename(self.get_show().name)
        # return f"e-{self.noco_id:05d}_{date}_{show}"

    def ref_nr(self) -> str:
        """
        Canonical reference number used in Omnia. Currently and (according to
        current planning) also in the future, this is the same as the file name
        prefix. However, as this may be changed one day, this method is already
        defined.
        """
        return self.file_name_prefix()

    async def omnia_description(self) -> tuple[str, bool]:
        """
        The description for the online publication. If none was specified during
        the upload, the description of the linked show is used. Bool is True if
        description was from upload itself. False if description originates from
        the linked show.
        """
        if self.description is not None and self.description != "":
            return self.description, True
        show = await self.cached_show
        return show.description, False

    def available_online_from(self) -> datetime:
        """
        Calculates the time at which the episode is to be published online.
        (First transmission time plus one hour.)
        """
        return self.planned_broadcast_at + timedelta(hours=1)

    def available_online_to(self) -> datetime:
        """
        Calculates the time when the episode should be de-published online.
        (First transmission time plus seven days and one hour.)
        """
        return self.planned_broadcast_at + timedelta(days=7, hours=1)
