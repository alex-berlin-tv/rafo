"""
Handles the export of upload entries from Baserow.
"""

from typing import Optional
from .import ManagementResult, Notification, Omnia, StreamType
from ..model import BaserowUpload, UploadState, UploadStates

from datetime import timedelta


DATE_FORMAT = "%d.%m.%Y %H:%M"


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
    def done(cls, data: dict[str, str]):
        return cls._done(
            "Formatinformationen wurden von Omnia geladen",
            f"Die Informationen zum zugehörigen Format wurden von Omnia geladen.",
            data,
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
            f"Die ID ({omnia_id}) des neu in Omnia angelegten Elements wurde in Baserow gespeichert.",
            None,
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Aktualisieren des Baserow Eintrags gescheitert")


class OmniaUploadExport:
    """Export upload entries from Baserow to Omnia."""

    def __init__(self, row_id: int):
        self.row_id = row_id

    async def run(self):
        ntf_class = InitNotification
        try:
            upload = BaserowUpload.by_id(self.row_id).one()
            yield ntf_class.done(upload).to_message()

            ntf_class = FetchShowNotification
            yield ntf_class.running().to_message()
            omnia_show_id, data = self.__fetch_omnia_show(upload)
            yield ntf_class.done(data).to_message()

            ntf_class = UploadNotification
            yield ntf_class.running().to_message()
            omnia_element_id, data = self.__upload_file(upload)
            yield ntf_class.done(data).to_message()

            ntf_class = MetadataNotification
            yield ntf_class.running(omnia_element_id).to_message()
            data = self.__set_metadata(omnia_element_id, upload)
            yield ntf_class.done(omnia_element_id, data).to_message()

            ntf_class = UpdateBaserowEntryNotification
            yield ntf_class.running(omnia_element_id).to_message()
            self.__update_baserow_entry(omnia_element_id, upload)
            yield ntf_class.done(omnia_element_id).to_message()

        except Exception as e:
            yield ntf_class.error(e).to_message()

        yield self.__close_connection()

    def __fetch_omnia_show(self, upload: BaserowUpload) -> tuple[int, dict[str, str]]:
        return (0, {})

    def __upload_file(self, upload: BaserowUpload) -> tuple[int, dict[str, str]]:
        omnia = Omnia.from_config()
        if upload.optimized_file is None:
            raise ValueError("upload field is none")
        if len(upload.optimized_file.root) < 1:
            raise ValueError("no upload file given")
        file = upload.optimized_file.root[0]
        if file.url is None:
            raise ValueError("first upload field entry has no url")

        name = upload.file_name_prefix()
        rsp = omnia.upload_by_url(
            StreamType.AUDIO,
            file.url,
            True,
            {"autoPublish": "1"},
            filename=name,
            ref_nr=name,
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
        })

    def __set_metadata(self, omnia_id: int, upload: BaserowUpload) -> dict[str, str]:
        if upload.description is not None and upload.description != "":
            description = upload.description
        else:
            description = upload.cached_show.description
        valid_from = upload.planned_broadcast_at + timedelta(hours=1)
        valid_to = upload.planned_broadcast_at + timedelta(days=1, hours=1)
        attributes = {
            "title": upload.name,
            "description": description,
            "releasedate": str(int(upload.planned_broadcast_at.timestamp())),
        }
        restrictions = {
            "validFrom": str(int(valid_from.timestamp())),
            "validUntil": str(int(valid_to.timestamp())),
        }

        omnia = Omnia.from_config()
        omnia.update(StreamType.AUDIO, omnia_id, attributes)
        omnia.update_restrictions(StreamType.AUDIO, omnia_id, restrictions)

        return {
            "Titel": attributes["title"],
            "Beschreibung": attributes["description"],
            "Erstsendedatum": upload.planned_broadcast_at.strftime(DATE_FORMAT),
            "Verfügbar ab": valid_from.strftime(DATE_FORMAT),
            "Verfügbar bis": valid_to.strftime(DATE_FORMAT),
        }

    def __update_baserow_entry(self, omnia_id: int, upload: BaserowUpload):
        BaserowUpload.update(
            upload.row_id,
            by_alias=True,
            omnia_id=omnia_id,
        )
        upload.update_state(
            UploadStates.OMNIA_PREFIX,
            UploadState.OMNIA_COMPLETE,
        )

    @staticmethod
    def __close_connection():
        return f"data: CLOSE CONNECTION\n\n"
