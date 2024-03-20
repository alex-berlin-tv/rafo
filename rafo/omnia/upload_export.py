"""
Handles the export of upload entries from Baserow.
"""

from .import ManagementResult, Notification, Omnia, StreamType
from ..model import BaserowUpload, UploadState, UploadStates

from datetime import timedelta


DATE_FORMAT = "%d.%m.%Y %H:%M"


class UploadExportNotification(Notification):
    @classmethod
    def init_done(cls, upload: BaserowUpload):
        return cls(
            target="init",
            title="Initialisiert",
            state="done",
            description="Eintrag wurde von Baserow geladen:",
            items={
                "Baserow ID": str(upload.row_id),
                "Name": upload.name,
                "Geplante Ausstrahlung": upload.planned_broadcast_at.strftime(DATE_FORMAT),
            },
        )

    @classmethod
    def init_failed(cls, e: Exception):
        return cls(
            target="init",
            title="Initialisierung fehlgeschlagen",
            state="error",
            description=str(e),
            items=None,
        )

    @classmethod
    def upload_running(cls):
        return cls(
            target="upload",
            title="Element wird in Omnia angelegt...",
            state="running",
            description="Es wird ein neues Element in Omnia für den Upload angelegt.",
            items=None,
        )

    @classmethod
    def upload_done(cls, data: dict[str, str]):
        return cls(
            target="upload",
            title="Element in Omnia angelegt",
            state="done",
            description=f"Das Element wurde in Omnia angelegt. Der Upload des Sendefiles läuft nun im Hintergrund weiter.",
            items=data,
        )

    @classmethod
    def metadata_running(cls, omnia_id: int):
        return cls(
            target="metadata",
            title="Metadaten werden in Omnia gesetzt...",
            state="running",
            description=f"Die Metadaten für das Omnia Element {omnia_id} werden gesetzt.",
            items=None,
        )

    @classmethod
    def metadata_done(cls, omnia_id: int, data: dict[str, str]):
        return cls(
            target="metadata",
            title="Metadaten in Omnia gesetzt",
            state="done",
            description=f"Die Metadaten für das Omnia Element {omnia_id} sind gesetzt.",
            items=data,
        )

    @classmethod
    def metadata_failed(cls, e: Exception):
        return cls(
            target="metadata",
            title="Setzten der Metadaten in Omnia gescheitert",
            state="error",
            description=f"Fehlermeldung: {e}",
            items=None,
        )

    @classmethod
    def upload_failed(cls, e: Exception):
        return cls(
            target="upload",
            title="Element in Omnia anlegen gescheitert",
            state="error",
            description=f"Fehlermeldung: {e}",
            items=None,
        )

    @classmethod
    def cover_running(cls):
        return cls(
            target="cover",
            title="Cover wird gesetzt...",
            state="running",
            description="Falls ein spezifisches Bild für die Episode vorhanden ist, wird dieses in Omnia hochgeladen. Andernfalls wird das für die Sendung festgelegte Bild in Omnia verwendet.",
            items=None,
        )

    @classmethod
    def cover_done(cls, data: dict[str, str]):
        return cls(
            target="upload",
            title="Element in Omnia angelegt",
            state="done",
            description=f"Das Element wurde in Omnia angelegt. Der Upload des Sendefiles läuft nun im Hintergrund weiter.",
            items=data,
        )

    @classmethod
    def cover_failed(cls, e: Exception):
        return cls(
            target="upload",
            title="Element in Omnia anlegen gescheitert",
            state="error",
            description=f"Fehlermeldung: {e}",
            items=None,
        )

    @classmethod
    def update_baserow_entry_running(cls, omnia_id: int):
        return cls(
            target="update_upload",
            title="Eintrag in Baserow wird aktualisiert...",
            state="running",
            description=f"Die ID ({omnia_id}) des neu in Omnia angelegten Elements wird in Baserow gespeichert.",
            items=None,
        )

    @classmethod
    def update_baserow_entry_done(cls, omnia_id: int):
        return cls(
            target="update_upload",
            title="Eintrag in Baserow ist aktualisiert",
            state="done",
            description=f"Die ID ({omnia_id}) des neu in Omnia angelegten Elements wurde in Baserow gespeichert.",
            items={},
        )

    @classmethod
    def update_baserow_entry_failed(cls, e: Exception):
        return cls(
            target="update_upload",
            title="Aktualisieren des Baserow Eintrags gescheitert",
            state="error",
            description=f"Fehlermeldung: {e}",
            items={},
        )

    def to_message(self) -> str:
        """Returns as a message for the SSE event source."""
        return f"data: {self.model_dump_json()}\n\n"


class OmniaUploadExport:
    """Export upload entries from Baserow to Omnia."""

    def __init__(self, row_id: int):
        self.row_id = row_id

    async def run(self):
        try:
            upload = BaserowUpload.by_id(self.row_id).one()
            yield UploadExportNotification.init_done(upload).to_message()
        except Exception as e:
            yield UploadExportNotification.init_failed(e).to_message()
            yield self.__close_connection()
            return

        try:
            yield UploadExportNotification.upload_running().to_message()
            omnia_id, data = self.__upload_file(upload)
            yield UploadExportNotification.upload_done(data).to_message()
        except Exception as e:
            yield UploadExportNotification.upload_failed(e).to_message()
            yield self.__close_connection()
            return

        try:
            yield UploadExportNotification.metadata_running(omnia_id).to_message()
            data = self.__set_metadata(omnia_id, upload)
            yield UploadExportNotification.metadata_done(omnia_id, data).to_message()
        except Exception as e:
            yield UploadExportNotification.metadata_failed(e).to_message()
            yield self.__close_connection()
            return

        try:
            yield UploadExportNotification.update_baserow_entry_running(omnia_id).to_message()
            self.__update_baserow_entry(omnia_id, upload)
            yield UploadExportNotification.update_baserow_entry_done(omnia_id).to_message()
        except Exception as e:
            yield UploadExportNotification.update_baserow_entry_failed(e).to_message()
            yield self.__close_connection()
            return

        yield self.__close_connection()

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
