from rafo.baserow import File, FileField
from .config import settings
from .ffmpeg import Metadata, Optimize, Silence, Waveform
from .log import logger
from .model import UploadState, UploadStates, get_nocodb_client, get_nocodb_project, BaserowUpload
from .noco_upload import Upload

from pathlib import Path
import shutil
import threading
from typing import Optional


class FileWorker:
    def __init__(self, raw_file: Path, cover_file: Optional[Path], temp_folder: Path, upload_id: int):
        self.raw_file = raw_file
        self.cover_file = cover_file
        self.temp_folder = temp_folder
        self.upload_id = upload_id
        self.count_lock = threading.Lock()
        self.finished_workers = 0
        self.upload = Upload(
            settings.nocodb_url,
            settings.nocodb_api_key,
            get_nocodb_client(),
            get_nocodb_project(),
        )
        self.__cached_upload: Optional[BaserowUpload] = None
        self.__file_name_prefix: Optional[str] = None

    def upload_raw(self):
        logger.debug(f"About to upload raw file {self.raw_file}")
        self.__upload_named_file(self.raw_file, "raw", "source_file")
        with self.count_lock:
            self.finished_workers += 1

    def upload_cover(self):
        if self.cover_file is None:
            logger.debug("No cover file available to be uploaded")
            return
        self.__upload_named_file(self.cover_file, "cover", "cover")
        with self.count_lock:
            self.finished_workers += 1

    def generate_waveform(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
        self.__upload().update_state(
            UploadStates.WAVEFORM_PREFIX,
            UploadState.WAVEFORM_RUNNING,
        )
        waveform = Waveform(gain, width, height, color)
        file_name = self.__file_name("waveform-raw", ".png")
        output_path = self.temp_folder / file_name
        try:
            err = waveform.run(
                self.raw_file,
                output_path,
            )
            self.__upload_named_file(output_path, "waveform", "waveform")
            # print("not migrated to Baserow yet, bye!")
            # return
            # self.upload.upload_file(
            #     output_path,
            #     file_name,
            #     settings.episode_table,
            #     settings.waveform_column,
            #     self.upload_id,
            # )
        except Exception:
            with self.count_lock:
                self.finished_workers += 1
            self.__upload().update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_ERROR,
            )
            raise
        if err is not None:
            self.__upload().update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_ERROR,
            )
        else:
            self.__upload().update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_COMPLETE,
            )
        logger.info(
            f"Waveform generated for {self.raw_file} and written to {output_path}")
        with self.count_lock:
            self.finished_workers += 1

    def optimize_file(self):
        self.__upload().update_state(
            UploadStates.OPTIMIZATION_PREFIX,
            UploadState.OPTIMIZATION_RUNNING,
        )
        file_name = self.__file_name("opt", ".mp3")
        output_path = self.temp_folder / file_name
        person = self.__upload().get_uploader()
        show = self.__upload().get_show()

        try:
            silence = Silence(self.raw_file)
            optimize = Optimize(self.raw_file, silence,
                                self.__upload(), person, show)
            optimize.run(output_path)
            duration = Metadata(output_path).formatted_duration()

            log = silence.log()
            if log == "":
                self.__upload().update_state(
                    UploadStates.OPTIMIZATION_PREFIX,
                    UploadState.OPTIMIZATION_COMPLETE,
                )
            else:
                self.__upload().update_state(
                    UploadStates.OPTIMIZATION_PREFIX,
                    UploadState.OPTIMIZATION_SEE_LOG,
                )

            log = f"{log}\nFinal running time: {duration}"
            self.__upload().update_optimizing_log(log)

            self.__upload_named_file(output_path, "opt", "optimized_file")

        except Exception:
            self.__upload().update_state(
                UploadStates.OPTIMIZATION_PREFIX,
                UploadState.OPTIMIZATION_ERROR,
            )
            with self.count_lock:
                self.finished_workers += 1
            raise

        with self.count_lock:
            self.finished_workers += 1

    def delete_temp_folder_on_completion(self):
        while self.finished_workers != 4:
            pass
        logger.debug(f"Delete temp folder {self.temp_folder}")
        shutil.rmtree(self.temp_folder)

    def __upload_named_file(
        self,
        path: Path,
        slug: str,
        field: str
    ):
        """Upload files with the required name-schema from the temp folder."""
        named_file = path.with_name(self.__file_name(
            slug, None)).with_suffix(path.suffix)
        if path != named_file:
            shutil.copy(path, named_file)

        name = self.__file_name(slug, None)
        logger.debug(f"About to upload {name} file {self.cover_file}")
        with open(named_file, "rb") as f:
            file_response = File.upload_file(f)

        file_response.original_name = name
        self.__upload().update(
            self.__upload().row_id,
            by_alias=True,
            **{field: FileField([file_response]).model_dump(mode="json")}
        )
        logger.info(
            f"{slug.title()} file {self.cover_file} uploaded to Baserow")

    def __upload(self) -> BaserowUpload:
        """Provides the (cached) Upload record."""
        if self.__cached_upload is None:
            self.__cached_upload = BaserowUpload.by_id(self.upload_id).one()
        return self.__cached_upload

    def __file_name(self, slug: str, extension: Optional[str]) -> str:
        """
        Cached method for getting a file name. Has to be cached as multiple methods
        of the file worker need a file name but getting it needs at least two API
        calls.

        If `extension` is `None` the method will not append any file extension.
        """
        if extension is None:
            extension = ""
        elif extension[0] != ".":
            extension = f".{extension}"
        if self.__file_name_prefix is None:
            self.__file_name_prefix = self.__upload().file_name_prefix()
        return f"{self.__file_name_prefix}-{slug}{extension}"
