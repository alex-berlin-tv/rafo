from pathlib import Path
import shutil
import threading
from typing import Optional

from rafo.baserow_orm import File, FileField
from rafo.ffmpeg_worker import Metadata, Optimize, Silence, Waveform
from rafo.log import logger
from rafo.model import UploadState, UploadStates, BaserowUpload


class FileWorker:
    def __init__(self, raw_file: Path, cover_file: Optional[Path], temp_folder: Path, upload: BaserowUpload):
        self.raw_file = raw_file
        self.cover_file = cover_file
        self.temp_folder = temp_folder
        self.upload = upload
        self.count_lock = threading.Lock()
        self.finished_workers = 0
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

    async def generate_waveform(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
        await self.upload.update_state(
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
        except Exception:
            with self.count_lock:
                self.finished_workers += 1
            await self.upload.update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_ERROR,
            )
            raise
        if err is not None:
            await self.upload.update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_ERROR,
            )
        else:
            await self.upload.update_state(
                UploadStates.WAVEFORM_PREFIX,
                UploadState.WAVEFORM_COMPLETE,
            )
        logger.info(
            f"Waveform generated for {self.raw_file} and written to {output_path}")
        with self.count_lock:
            self.finished_workers += 1

    async def optimize_file(self):
        await self.upload.update_state(
            UploadStates.OPTIMIZATION_PREFIX,
            UploadState.OPTIMIZATION_RUNNING,
        )
        file_name = self.__file_name("opt", ".mp3")
        output_path = self.temp_folder / file_name

        try:
            silence = Silence(self.raw_file)
            optimize = Optimize(
                self.raw_file, silence,
                self.upload,
                await self.upload.cached_uploader,
                await self.upload.cached_show,
            )
            optimize.run(output_path)

            log = silence.log()
            if log == "":
                await self.upload.update_state(
                    UploadStates.OPTIMIZATION_PREFIX,
                    UploadState.OPTIMIZATION_COMPLETE,
                )
                duration = round(Metadata(output_path).duration())
                self.upload.update(self.upload.row_id, duration=duration)
            else:
                await self.upload.update_state(
                    UploadStates.OPTIMIZATION_PREFIX,
                    UploadState.OPTIMIZATION_SEE_LOG,
                )
                self.upload.update(self.upload.row_id, optimization_log=log)

            self.__upload_named_file(output_path, "opt", "optimized_file")

        except Exception:
            await self.upload.update_state(
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
        self.upload.update(
            self.upload.row_id,
            by_alias=True,
            **{field: FileField([file_response]).model_dump(mode="json")}
        )
        logger.info(
            f"{slug.title()} file {self.cover_file} uploaded to Baserow")

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
            self.__file_name_prefix = self.upload.file_name_prefix()
        return f"{self.__file_name_prefix}-{slug}{extension}"
