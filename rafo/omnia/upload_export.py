"""
Handles the export of upload entries from Baserow.
"""

import enum
from pydantic.main import BaseModel
from pydantic.types import Base64UrlBytes

from rafo.omnia.omnia import MediaResult, MediaResultGeneral, Response
from .import ManagementResult, Notification, Omnia, StreamType
from ..model import BaserowUpload, UploadState, UploadStates

from datetime import timedelta


DATE_FORMAT = "%d.%m.%Y %H:%M"


class OmniaShow(BaseModel):
    """Information related to a show which is needed."""
    item_id: int
    title: str

    @classmethod
    def from_omnia_response(cls, rsp: Response):
        if not isinstance(rsp.result, MediaResult):
            raise ValueError(
                f"result field in Omnia response is not of type MediaResult"
            )
        if not isinstance(rsp.result.general, MediaResultGeneral):
            raise ValueError(
                f"result.general field in Omnia response is not of type MediaResultGeneral {rsp}"
            )

        return cls(
            item_id=rsp.result.general.item_id,
            title=rsp.result.general.title,
        )


class CoverSource(int, enum.Enum):
    """States the source of the cover."""

    UPLOAD = 0
    """Custom cover as part of the upload submission."""
    SHOW = 1
    """General cover of the show."""

    def info_key(self) -> str:
        if self is CoverSource.UPLOAD:
            return "Bild stammt aus Upload"
        if self is CoverSource.SHOW:
            return "Standardbild des Formats"
        return "UNKNOWN"

    def info_value(self) -> str:
        if self is CoverSource.UPLOAD:
            return "Der:die Produzent:in hat beim Upload ein Cover hochgeladen."
        if self is CoverSource.SHOW:
            return "Der:die Produzent:in hat beim Upload kein Cover hochgeladen, das Standartcover des Formats wurde gesetzt."
        return "UNKNOWN"


class CoverInfo(BaseModel):
    """Result information from the cover operation."""
    source: CoverSource
    thumbnail: str


class InitNotification(Notification):
    target = "init"

    @classmethod
    def done(cls, upload: BaserowUpload):
        return cls._done(
            "Initialisiert",
            "Daten wurde von Baserow geladen",
            {
                "Baserow ID": str(upload.row_id),
                "Name": upload.name,
                "Geplante Ausstrahlung": upload.planned_broadcast_at.strftime(DATE_FORMAT),
            },
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Initialisierung fehlgeschlagen")


class FetchShowNotification(Notification):
    target = "show"

    @classmethod
    def running(cls):
        return cls._running(
            "Formatinformationen von Omnia laden...",
            "Informationen zum Upload gehörende Format werden von Omnia abgerufen.",
            None,
        )

    @classmethod
    def done(cls, show: OmniaShow):
        return cls._done(
            "Formatinformationen wurden von Omnia geladen",
            f"Die Informationen zum zugehörigen Format wurden von Omnia geladen.",
            {
                "Omnia Show ID": str(show.item_id),
                "Omnia Show Titel": show.title,
            }
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Abfragen der Sendung in Omnia gescheitert")


class UploadNotification(Notification):
    target = "upload"

    @classmethod
    def running(cls):
        return cls._running(
            "Element wird in Omnia angelegt...",
            "Es wird ein neues Element in Omnia für den Upload angelegt.",
            None,
        )

    @classmethod
    def done(cls, data: dict[str, str]):
        return cls._done(
            "Element in Omnia angelegt",
            f"Das Element wurde in Omnia angelegt. Der Upload des Sendefiles läuft nun im Hintergrund weiter.",
            data,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Element in Omnia anlegen gescheitert")


class MetadataNotification(Notification):
    target = "metadata"

    @classmethod
    def running(cls, omnia_id: int):
        return cls._running(
            "Metadaten werden in Omnia gesetzt...",
            f"Die Metadaten für das Omnia Element {omnia_id} werden gesetzt.",
            None,
        )

    @classmethod
    def done(cls, omnia_id: int, data: dict[str, str]):
        return cls._done(
            "Metadaten in Omnia gesetzt",
            f"Die Metadaten für das Omnia Element {omnia_id} sind gesetzt.",
            data,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Setzten der Metadaten in Omnia gescheitert")


class CoverNotification(Notification):
    target = "cover"

    @classmethod
    def running(cls):
        return cls._running(
            "Upload Cover",
            f"Das Cover wird nach Omnia hochgeladen. Dieser Vorgang kann ein paar Minuten in Anspruch nehmen...",
            None,
        )

    @classmethod
    def done(cls, data: CoverInfo):
        return cls._done(
            "Cover gesetzt",
            f"Das Cover wurde auf Omnia angelegt und mit dem Element verknüpft.",
            {data.source.info_key(): data.source.info_value()},
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Anlegen des Covers in Omnia gescheitert")


class UpdateBaserowEntryNotification(Notification):
    target = "update_baserow_entry"

    @classmethod
    def running(cls, omnia_id: int):
        return cls._running(
            "Eintrag in Baserow wird aktualisiert...",
            f"Die ID ({omnia_id}) des neu in Omnia angelegten Elements wird in Baserow gespeichert.",
            None,
        )

    @classmethod
    def done(cls, omnia_id: int):
        return cls._done(
            "Eintrag in Baserow ist aktualisiert",
            f"Der Upload Eintrag in Baserow wurde aktualisiert.",
            None,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Aktualisieren des Baserow Eintrags gescheitert")


class OmniaUploadExport:
    """Export upload entries from Baserow to Omnia."""

    def __init__(self, row_id: int):
        self.row_id = row_id
        self.omnia = Omnia.from_config()

    async def run(self):
        ntf_class = InitNotification
        try:
            upload = await self.__fetch_baserow_upload()
            yield ntf_class.done(upload).to_message()

            ntf_class = FetchShowNotification
            yield ntf_class.running().to_message()
            omnia_show = await self.__fetch_omnia_show(upload)
            yield ntf_class.done(omnia_show).to_message()

            ntf_class = UploadNotification
            yield ntf_class.running().to_message()
            omnia_item_id, data = await self.__upload_file(upload)
            yield ntf_class.done(data).to_message()

            ntf_class = MetadataNotification
            yield ntf_class.running(omnia_item_id).to_message()
            data = await self.__set_metadata(
                omnia_item_id, omnia_show.item_id, upload
            )
            yield ntf_class.done(omnia_item_id, data).to_message()

            ntf_class = CoverNotification
            yield ntf_class.running().to_message()
            cover_info = await self.__set_cover(omnia_item_id, upload)
            yield ntf_class.done(cover_info).to_message()

            ntf_class = UpdateBaserowEntryNotification
            yield ntf_class.running(omnia_item_id).to_message()
            await self.__update_baserow_entry(omnia_item_id, upload)
            yield ntf_class.done(omnia_item_id).to_message()

        except Exception as e:
            yield ntf_class.error(e).to_message()

        yield self.__close_connection()

    async def __fetch_baserow_upload(self) -> BaserowUpload:
        return BaserowUpload.by_id(self.row_id).one()

    async def __fetch_omnia_show(self, upload: BaserowUpload) -> OmniaShow:
        if upload.cached_show.omnia_id is None:
            raise ValueError(
                f"omnia ID of show '{upload.cached_show.name}' (ID {upload.cached_show.row_id}) in Baserow is not set"
            )
        rsp = self.omnia.by_id(StreamType.SHOW, upload.cached_show.omnia_id)
        return OmniaShow.from_omnia_response(rsp)

    async def __upload_file(self, upload: BaserowUpload) -> tuple[int, dict[str, str]]:
        if upload.optimized_file is None:
            raise ValueError("upload field is none")
        if len(upload.optimized_file.root) < 1:
            raise ValueError("no upload file given")
        file = upload.optimized_file.root[0]
        if file.url is None:
            raise ValueError("first upload field entry has no url")
        name = upload.file_name_prefix()

        rsp = self.omnia.upload_by_url(
            StreamType.AUDIO,
            file.url,
            True,
            {},
            filename=name,
            ref_nr=name,
            auto_publish=True,
            notes=upload.comment_producer,
        )
        if not isinstance(rsp.result, ManagementResult):
            raise ValueError(
                "'result' field in response is not of type ManagementResult"
            )
        if rsp.result.item_update is None:
            raise ValueError(
                "field 'itemupdate' is null in response"
            )
        omnia_id = rsp.result.item_update.generated_id
        return (omnia_id, {
            "Omnia Element ID": str(omnia_id),
            "Omnia Referenznummer": name,
            "Omnia Dateiname": name,
            "Element wird automatisch publiziert": "Ja",
            "Hinweis Upload": upload.comment_producer if upload.comment_producer else "n.n.",
        })

    async def __set_metadata(self, omnia_item_id: int, omnia_show_id: int, upload: BaserowUpload) -> dict[str, str]:
        if upload.description is not None and upload.description != "":
            description = upload.description
            description_src = "von Upload Eintrag"
        else:
            description = upload.cached_show.description
            description_src = "von Format Beschreibung, da dem Upload keine Beschreibung hinzugefügt wurde"
        valid_from = upload.planned_broadcast_at + timedelta(hours=1)
        valid_to = upload.planned_broadcast_at + timedelta(days=7, hours=1)
        attributes = {
            "title": upload.name,
            "description": description,
            "releasedate": str(int(upload.planned_broadcast_at.timestamp())),
        }
        restrictions = {
            "validFrom": str(int(valid_from.timestamp())),
            "validUntil": str(int(valid_to.timestamp())),
        }

        self.omnia.update(StreamType.AUDIO, omnia_item_id, attributes)
        self.omnia.update_restrictions(
            StreamType.AUDIO,
            omnia_item_id,
            restrictions
        )
        self.omnia.connect_show(
            StreamType.AUDIO, omnia_item_id, omnia_show_id
        )

        return {
            "Titel": attributes["title"],
            "Beschreibung": f"{attributes['description']} ({description_src})",
            "Erstsendedatum": upload.planned_broadcast_at.strftime(DATE_FORMAT),
            "Verfügbar ab": valid_from.strftime(DATE_FORMAT),
            "Verfügbar bis": valid_to.strftime(DATE_FORMAT),
            "Verknüpft mit Sendung": f"{omnia_show_id} (ID)",
        }

    async def __set_cover(self, omnia_item_id: int, upload: BaserowUpload) -> CoverInfo:
        if upload.cover is not None and len(upload.cover.root) > 0:
            if len(upload.cover.root) != 1:
                raise ValueError(
                    f"upload element in Baserow with ID {upload.row_id} has more than one cover set (got {len(upload.cover.root)} instead)"
                )
            url = upload.cover.root[0].url
            if url is None:
                raise ValueError(
                    f"url in cover field of upload element in Baserow with ID {upload.row_id} is None"
                )
            source = CoverSource.UPLOAD
        else:
            if upload.cached_show.cover is None:
                raise ValueError(
                    f"upload element in Baserow with ID {upload.row_id} and show element with ID {upload.cached_show.row_id} both have no cover set"
                )
            if len(upload.cached_show.cover.root) != 1:
                raise ValueError(
                    f"show element in Baserow with ID {upload.cached_show.row_id} has not exactly one cover set (got {len(upload.cached_show.cover.root)} instead)"
                )
            url = upload.cached_show.cover.root[0].url
            if url is None:
                raise ValueError(
                    f"url in cover field of show element in Baserow with ID {upload.cached_show.row_id} is None"
                )
            source = CoverSource.SHOW
        self.omnia.update_cover(StreamType.AUDIO, omnia_item_id, url)
        return CoverInfo(
            source=source,
            thumbnail="",
        )

    async def __update_baserow_entry(self, omnia_item_id: int, upload: BaserowUpload):
        BaserowUpload.update(
            upload.row_id,
            by_alias=True,
            omnia_id=omnia_item_id,
        )
        upload.update_state(
            UploadStates.OMNIA_PREFIX,
            UploadState.OMNIA_COMPLETE,
        )

    @staticmethod
    def __close_connection():
        return f"data: CLOSE CONNECTION\n\n"
