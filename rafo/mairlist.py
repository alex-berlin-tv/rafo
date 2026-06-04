from datetime import datetime
from pathlib import Path

from rafo.config import settings
from rafo.utils import Notification
from rafo.model import BaserowUpload, UploadState


DATE_FORMAT = "%d.%m.%Y %H:%M"


class InvalidBaserowUploadStateError(Exception):
    """
    Thrown when the state of a Baserow upload indicates that it has already been
    exported to mAirList.
    """

    def __init__(
        self, baserow_id: int, baserow_name: str, baserow_planned_broadcast_at: datetime
    ):
        self.baserow_id = baserow_id
        self.baserow_name = baserow_name
        self.baserow_planned_broadcast_at = baserow_planned_broadcast_at


class BaserowFileError(Exception):
    """
    Thrown when a file is not found in Baserow.
    """

    def __init__(
        self, baserow_id: int, baserow_name: str, baserow_planned_broadcast_at: datetime
    ):
        self.baserow_id = baserow_id
        self.baserow_name = baserow_name
        self.baserow_planned_broadcast_at = baserow_planned_broadcast_at


class FileExistsError(Exception):
    """
    Thrown when the file to be copied already exists on the media share.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path


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
                "Geplante Ausstrahlung": upload.planned_broadcast_at.strftime(
                    DATE_FORMAT
                ),
            },
        )

    @classmethod
    def invalid_state_error(cls, e: InvalidBaserowUploadStateError):
        return cls._error(
            "Der Eintrag scheint bereits nach mAirList exportiert worden zu sein.",
            "Das Feld 'Status' des zu exportierenden Uploads enthält den Status 'mAirList: Liegt auf \\\\Distribution'. Dies ist ein Hinweis darauf, dass für diesen Upload bereits ein Export nach mAirList durchgeführt wurde. Soll der Export erneut gestartet werden, muss das Feld 'Status' in Baserow manuell auf 'mAirList: Ausstehend' gesetzt werden.",
            {
                "Baserow ID": str(e.baserow_id),
                "Name": e.baserow_name,
                "Geplante Ausstrahlung": e.baserow_planned_broadcast_at.strftime(
                    DATE_FORMAT
                ),
            },
        )
    
    @classmethod
    def baserow_file_error(cls, e: BaserowFileError):
        return cls._error(
            "Die Mediendatei wurde in Baserow nicht gefunden.",
            "Weder die optimierte noch die manuelle Version der Datei wurde in Baserow gefunden. Bitte stelle sicher, dass die Datei im Eintrag in Baserow vorhanden ist.",
            {
                "Baserow ID": str(e.baserow_id),
                "Name": e.baserow_name,
                "Geplante Ausstrahlung": e.baserow_planned_broadcast_at.strftime(
                    DATE_FORMAT
                ),
            },
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(e, "Initialisierung fehlgeschlagen")


class MediaShareValidationNotification(Notification):
    target = "media_share_validation"

    @classmethod
    def running(cls):
        return cls._running(
            "Validierung des mAirList SMB Shares",
            "Der mAirList SMB Share wird validiert.",
            None,
        )

    @classmethod
    def done(cls, file_path: str):
        return cls._done(
            "mAirList SMB Share wurde validiert",
            "Der mAirList SMB Share wurde erfolgreich validiert.",
            {
                "Dateipfad": file_path,
            },
        )

    @classmethod
    def file_exists_error(cls, e: FileExistsError):
        return cls._error(
            "Die Datei existiert bereits auf dem mAirList SMB Share",
            "Die Datei existiert bereits auf dem mAirList SMB Share. Bitte überprüfe die Datei und lösche sie manuell.",
            {
                "Dateipfad": e.file_path,
            },
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(
            e, "Validierung des mAirList SMB Shares fehlgeschlagen"
        )


class CopyFileNotification(Notification):
    target = "copy"

    @classmethod
    def running(cls, file_path: str):
        return cls._running(
            "Kopieren der Datei auf den mAirList SMB Share",
            "Die Datei wird auf den mAirList SMB Share kopiert.",
            {
                "Dateipfad": file_path,
            },
        )

    @classmethod
    def done(cls, file_path: str):
        return cls._done(
            "Datei auf dem mAirList SMB Share kopiert",
            "Die Datei wurde erfolgreich auf den mAirList SMB Share kopiert.",
            {
                "Dateipfad": file_path,
            },
        )

    @classmethod
    def error(cls, e: Exception):
        return cls.from_exception(
            e, "Kopieren der Datei auf den mAirList SMB Share fehlgeschlagen"
        )


class UpdateBaserowEntryNotification(Notification):
    target = "update_baserow_entry"

    @classmethod
    def running(cls, baserow_id: int):
        return cls._running(
            "Eintrag in Baserow wird aktualisiert...",
            f"Der Status des Uploads (ID {baserow_id}) wird in Baserow aktualisiert.",
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


class MAirListExport:
    """
    Export upload entries from Baserow to mAirList. By copying the file to the
    SMB share mAirList uses as it's data backend.
    """

    def __init__(self, row_id: int):
        self.row_id = row_id

    async def run(self):
        ntf_class = InitNotification
        init_ntf_class = ntf_class
        try:
            upload = await self.__fetch_baserow_upload()
            yield ntf_class.done(upload).to_message()
        except InvalidBaserowUploadStateError as e:
            yield init_ntf_class.invalid_state_error(e).to_message()
        except Exception as e:
            yield ntf_class.error(e).to_message()

    async def __fetch_baserow_upload(self) -> BaserowUpload:
        rsp = await BaserowUpload.by_id(self.row_id)
        rsl = rsp.one()
        if UploadState.MAIRLIST_COMPLETE in rsl.state_enum.values():
            raise InvalidBaserowUploadStateError(
                rsl.row_id, rsl.name, rsl.planned_broadcast_at
            )
        return rsl

    @staticmethod
    def __path(upload: BaserowUpload) -> Path:
        return Path(settings.mairlist_media_share) / MAirListExport.__folder_name(
            upload
        )

    @staticmethod
    def __folder_name(upload: BaserowUpload) -> str:
        return upload.planned_broadcast_at.strftime("%Y-%m")
