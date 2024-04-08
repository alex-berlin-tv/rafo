"""
Handles the export of upload entries from Baserow.
"""

from datetime import datetime
import enum
from typing import Any, Optional
from pydantic.main import BaseModel


from . import ManagementResult, MediaResult, MediaResultGeneral, Response, Notification, Omnia, StreamType
from ..config import settings
from ..model import BaserowUpload, UploadState, UploadStates


DATE_FORMAT = "%d.%m.%Y %H:%M"


class OmniaIDNotEmptyError(Exception):
    """
    Thrown when a Baserow entry to be exported to Omnia already contains a ID.
    """

    def __init__(self, baserow_id: int, baserow_name: str, omnia_id: Optional[int]):
        self.baserow_id = baserow_id
        self.baserow_name = baserow_name
        self.omnia_id = omnia_id


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
    def omnia_id_not_empty(cls, e: OmniaIDNotEmptyError):
        return cls._error(
            "Der Eintrag scheint bereits nach Omnia exportiert worden zu sein.",
            "Das Feld 'Omnia ID' des zu exportierenden Uploads ist bereits gesetzt. Dies ist ein Hinweis darauf, dass für diesen Upload bereits ein Export nach Omnia durchgeführt wurde. Soll der Export erneut gestartet werden, muss das Feld 'Omnia ID' in Baserow manuell gelöscht werden.",
            {
                "Baserow ID": str(e.baserow_id),
                "Name": e.baserow_name,
                "Omnia ID": str(e.omnia_id),
            },
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Initialisierung fehlgeschlagen")


class CheckRefnrNotification(Notification):
    target = "refnr"

    @classmethod
    def running(cls, ref_nr: str):
        return cls._running(
            "Check auf bereits existierende Einträge in Omnia",
            f"Es wird überprüft, ob in Omnia bereits ein Element mit der Referenz '{ref_nr}' vorhanden ist.",
            None,
        )

    @classmethod
    def done(cls, ref_nr: str):
        return cls._done(
            "Keine Dublette in Omnia gefunden",
            f"Auf Omnia existiert noch kein Element mit der Referenz '{ref_nr}'.",
            None,
        )

    @classmethod
    def warning(cls, ref_nr: str, data: dict[str, str]):
        return cls._warning(
            "Eintrag mit Referenznummer bereits vorhanden",
            f"Achtung: Nach dem Upload befindet sich _mindestens_ ein Elemente auf Omnia mit der Referenznummer '{ref_nr}'. Dies deutet in aller Regel auf einen mehrfachen Export hin. Der Export wird fortgesetzt. Bitte führe eine manuelle Überprüfung durch.",
            data,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Abfragen nach Referenz-Nummer gescheitert")


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
            },
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
            f"Das Cover wird nach Omnia hochgeladen. Dieser Vorgang kann einige Minuten in Anspruch nehmen...",
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
    def done(cls):
        return cls._done(
            "Eintrag in Baserow ist aktualisiert",
            f"Der Upload Eintrag in Baserow wurde aktualisiert.",
            None,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Aktualisieren des Baserow Eintrags gescheitert")


class OmniaValidationNotification(Notification):
    target = "omnia_validation"

    @classmethod
    def running(cls, omnia_id: int):
        return cls._running(
            "Eintrag wird auf Omnia validiert...",
            f"Das neu in Omnia (ID: {omnia_id}) angelegte Element wird validiert.",
            None,
        )

    @classmethod
    def done(cls, omnia_id: int):
        return cls._done(
            "Eintrag auf Omnia wurde validiert",
            f"Es konnten keine Probleme mit dem neue Eintrag in Omnia (ID {omnia_id}) festgestellt werden. Der Export ist hiermit erfolgreich beendet. 🎉",
            None,
            copy_values={"Omnia ID": str(omnia_id)},
        )

    @classmethod
    def warning(cls, omnia_id: int, data: dict[str, str]):
        return cls._warning(
            "Eintrag auf Omnia nicht korrekt",
            f"Der Omnia Eintrag (ID: {omnia_id}) scheint nicht korrekt zu sein. Bitte überprüfe den Eintrag.",
            data,
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
        init_ntf_class = ntf_class
        try:
            upload = await self.__fetch_baserow_upload()
            yield ntf_class.done(upload).to_message()

            ntf_class = FetchShowNotification
            yield ntf_class.running().to_message()
            omnia_show = await self.__fetch_omnia_show(upload)
            yield ntf_class.done(omnia_show).to_message()

            ntf_class = CheckRefnrNotification
            yield ntf_class.running(upload.ref_nr()).to_message()
            ref_check_rsl = await self.__check_ref_nr(upload.ref_nr())
            if ref_check_rsl:
                yield ntf_class.warning(upload.ref_nr(), ref_check_rsl).to_message()
            else:
                yield ntf_class.done(upload.ref_nr()).to_message()

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
            yield ntf_class.done().to_message()

            ntf_class = OmniaValidationNotification
            yield ntf_class.running(omnia_item_id).to_message()
            validation_rsl = await self.__omnia_validation(omnia_item_id, upload)
            if len(validation_rsl) > 0:
                yield ntf_class.warning(omnia_item_id, validation_rsl).to_message()
            else:
                yield ntf_class.done(omnia_item_id).to_message()
        except OmniaIDNotEmptyError as e:
            yield init_ntf_class.omnia_id_not_empty(e).to_message()
        except Exception as e:
            yield ntf_class.error(e).to_message()

        yield self.__close_connection()

    async def __fetch_baserow_upload(self) -> BaserowUpload:
        rsp = await BaserowUpload.by_id(self.row_id)
        rsl = rsp.one()
        if rsl.omnia_id is not None or (rsl.omnia_id is not None and rsl.omnia_id < 1):
            raise OmniaIDNotEmptyError(self.row_id, rsl.name, rsl.omnia_id)
        return rsl

    async def __fetch_omnia_show(self, upload: BaserowUpload) -> OmniaShow:
        show = await upload.cached_show
        if show.omnia_id is None:
            raise ValueError(
                f"omnia ID of show '{show.name}' (ID {show.row_id}) in Baserow is not set"
            )
        rsp = await self.omnia.by_id(StreamType.SHOW, show.omnia_id, True)
        return OmniaShow.from_omnia_response(rsp)

    async def __check_ref_nr(self, ref_nr: str) -> Optional[dict[str, str]]:
        rsp = await self.omnia.by_reference(StreamType.AUDIO, ref_nr, True)
        if rsp.result is None:
            return None
        if not isinstance(rsp.result, MediaResult):
            raise ValueError(
                "'result' field in response is not of type MediaResult"
            )
        return {
            "Schon bestehender Omnia Eintrag": f"ID: {rsp.result.general.item_id}, '{rsp.result.general.title}'",
            "Achtung": f"Es kann sein, dass _mehr_ als nur ein Eintrag mit der Referenz '{ref_nr}' bereits auf Omnia vorhanden ist! Du musst dies manuell prüfen."
        }

    async def __upload_file(self, upload: BaserowUpload) -> tuple[int, dict[str, str]]:
        if upload.optimized_file is None:
            raise ValueError("upload field is none")
        if len(upload.optimized_file.root) < 1:
            raise ValueError("no upload file given")
        file = upload.optimized_file.root[0]
        if file.url is None:
            raise ValueError("first upload field entry has no url")

        rsp = await self.omnia.upload_by_url(
            StreamType.AUDIO,
            file.url,
            True,
            {},
            filename=upload.file_name_prefix(),
            ref_nr=upload.ref_nr(),
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
            "Omnia Referenznummer": upload.ref_nr(),
            "Omnia Dateiname": upload.file_name_prefix(),
            "Element wird automatisch publiziert": "Ja",
            "Hinweis Upload": upload.comment_producer if upload.comment_producer else "n.n.",
        })

    async def __set_metadata(self, omnia_item_id: int, omnia_show_id: int, upload: BaserowUpload) -> dict[str, str]:
        description, description_from_upload = await upload.omnia_description()
        if description_from_upload:
            description_src = "von Upload Eintrag"
        else:
            description_src = "von Format Beschreibung, da dem Upload keine Beschreibung hinzugefügt wurde"
        valid_from = await upload.available_online_from()
        valid_to = await upload.available_online_to()
        attributes = {
            "title": upload.name,
            "description": description,
            "releasedate": Omnia.convert_dateformat(upload.planned_broadcast_at),
        }
        restrictions = {
            "validFrom": Omnia.convert_dateformat(valid_from),
        }
        if valid_to.timestamp() != 0:
            restrictions["validUntil"] = Omnia.convert_dateformat(valid_to)
            valid_to_info = valid_to.strftime(DATE_FORMAT)
        else:
            valid_to_info = "KEIN Depublikationsdatum gesetzt"

        await self.omnia.update(StreamType.AUDIO, omnia_item_id, attributes)
        await self.omnia.update_restrictions(
            StreamType.AUDIO,
            omnia_item_id,
            restrictions
        )
        await self.omnia.connect_show(
            StreamType.AUDIO, omnia_item_id, omnia_show_id
        )
        connected_shows: list[str] = [str(omnia_show_id)]
        if (await upload.cached_show).is_radio():
            for show_id in settings.shows_for_all_upload_exports:
                await self.omnia.connect_show(
                    StreamType.AUDIO, omnia_item_id, show_id
                )
                connected_shows.append(str(show_id))
        return {
            "Titel": attributes["title"],
            "Beschreibung": f"{attributes['description']} ({description_src})",
            "Erstsendedatum": upload.planned_broadcast_at.strftime(DATE_FORMAT),
            "Verfügbar ab": valid_from.strftime(DATE_FORMAT),
            "Verfügbar bis": valid_to_info,
            "Verknüpft mit Sendung": f"{', '.join(connected_shows)} (ID's)",
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
            show = await upload.cached_show
            if show.cover is None:
                raise ValueError(
                    f"upload element in Baserow with ID {upload.row_id} and show element with ID {show.row_id} both have no cover set"
                )
            if len(show.cover.root) != 1:
                raise ValueError(
                    f"show element in Baserow with ID {show.row_id} has not exactly one cover set (got {len(show.cover.root)} instead)"
                )
            url = show.cover.root[0].url
            if url is None:
                raise ValueError(
                    f"url in cover field of show element in Baserow with ID {show.row_id} is None"
                )
            source = CoverSource.SHOW
        await self.omnia.update_cover(StreamType.AUDIO, omnia_item_id, url)
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
        await upload.update_state(
            UploadStates.OMNIA_PREFIX,
            UploadState.OMNIA_COMPLETE,
        )

    async def __omnia_validation(self, omnia_item_id: int, upload: BaserowUpload) -> dict[str, str]:
        rsp = await self.omnia.by_id(
            StreamType.AUDIO,
            omnia_item_id,
            True,
            parameters={
                "additionalFields": "description,releasedate",
                "addConnectedMedia": "shows",
            },
        )
        if not isinstance(rsp.result, MediaResult):
            raise ValueError(
                f"'result' field in response is not of type MediaResult got {type(rsp.result)} instead"
            )
        if rsp.result.publishing_data is None:
            raise ValueError(
                "'result.publishingdata' field is None, expected PublishingData"
            )
        rsl: dict[str, str] = {}
        self.__validate_field(
            rsl,
            "Titel",
            upload.name,
            rsp.result.general.title,
        )
        self.__validate_field(
            rsl,
            "Beschreibung",
            (await upload.omnia_description())[0],
            rsp.result.general.description,
        )
        self.__validate_show_field(
            rsl,
            "Verknüpfte Sendung",
            (await upload.cached_show).omnia_id,
            rsp.result,
        )
        self.__validate_field(
            rsl,
            "Erstsendedatum",
            upload.planned_broadcast_at,
            rsp.result.general.release_date,
        )
        self.__validate_field(
            rsl,
            "Verfügbar ab (Desktop)",
            await upload.available_online_from(),
            rsp.result.publishing_data.valid_from_desktop,
        )
        self.__validate_field(
            rsl,
            "Verfügbar bis (Desktop)",
            await upload.available_online_to(),
            rsp.result.publishing_data.valid_until_desktop,
        )
        self.__validate_field(
            rsl,
            "Verfügbar ab (Mobil)",
            await upload.available_online_from(),
            rsp.result.publishing_data.valid_from_mobile,
        )
        self.__validate_field(
            rsl,
            "Verfügbar bis (Mobil)",
            await upload.available_online_to(),
            rsp.result.publishing_data.valid_until_mobile,
        )
        return rsl

    @staticmethod
    def __validate_field(rsl: dict[str, str], name: str, expected: Any, actual: Any):
        if expected == actual:
            return
        if isinstance(expected, datetime) and isinstance(actual, datetime):
            unix_epoch = datetime.fromtimestamp(0)
            if expected == unix_epoch and actual == unix_epoch:
                expected = "Nicht gesetzt"
                actual = "Nicht gesetzt"
            else:
                expected = expected.strftime(DATE_FORMAT)
                actual = actual.strftime(DATE_FORMAT)
        rsl[name] = f"Erwartet: '{expected}'; tatsächlich auf Omnia: '{actual}'."

    @staticmethod
    def __validate_show_field(rsl: dict[str, str], name: str, expected: Optional[int], omnia_rsl: MediaResult):
        if expected is None:
            raise ValueError(
                f"omnia id field in linked show for upload in Baserow is None"
            )
        if omnia_rsl.connected_media is None:
            rsl[name] = "Kein Format verknüpft."
            return
        if "shows" not in omnia_rsl.connected_media:
            rsl[name] = "Keine Format verknüpft."
            return
        ids = [show.item_id for show in omnia_rsl.connected_media["shows"]]
        if expected not in ids:
            rsl[name] = f"Verknüpfung mit Format {expected} fehlt."
        # rsp.result.connected_media["shows"],

    @staticmethod
    def __close_connection():
        return f"data: CLOSE CONNECTION\n\n"
