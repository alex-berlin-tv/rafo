from . import VERSION
from .baserow import TableLinkField
from .config import settings
from .file_worker import FileWorker
from .log import logger
from .mail import Mail
from .model import BaserowPerson, BaserowShow, BaserowUpload, ProducerUploadData, UploadStates
from .omnia.upload_export import OmniaUploadExport

import datetime
from uuid import uuid4
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, ValueTarget
from streaming_form_data.validators import MaxSizeValidator, ValidationError

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html.jinja2", {"request": request, "version": VERSION})


@app.get("/help")
async def help(request: Request):
    return templates.TemplateResponse("help.html.jinja2", {"request": request, "version": VERSION})


@app.get("/upload/{uuid}")
async def upload(
    request: Request,
    uuid: str,
):
    data = {
        "request": request,
        "requested_uuid": uuid,
        "base_url": settings.base_url,
        "version": VERSION,
    }
    return templates.TemplateResponse("upload.html.jinja2", data)


@app.get("/upload/{id}/omnia_export")
async def upload_omnia_export(
    request: Request,
    id: int,
    key: str,
):
    if key != settings.webhook_secret:
        raise HTTPException(
            status_code=403,
            detail="operation forbidden"
        )
    data = {
        "request": request,
        "base_url": settings.base_url,
        "version": VERSION,
    }
    return templates.TemplateResponse("upload_omnia_export.html.jinja2", data)


@app.get("/api/producer_for_upload/{uuid}")
async def producer_for_upload_info(
    uuid: str,
):
    try:
        data = await ProducerUploadData.from_db(uuid)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Unter dieser URL kann kein Formular gefunden werden. Stelle bitte sicher, dass du den Link korrekt kopiert hast und probiere es nochmals.")
    except Exception as e:
        # TODO: Log this
        raise HTTPException(
            status_code=500,
            detail=f"Exception, {e}",
        )
    return data


@app.get("/api/upload/{id}/omnia_export")
async def api_upload_omnia_export(
    request: Request,
    id: int,
    key: str,
):
    if key != settings.webhook_secret:
        raise HTTPException(
            status_code=403,
            detail="operation forbidden"
        )
    export = OmniaUploadExport(id)
    return StreamingResponse(
        export.run(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class MaxBodySizeException(Exception):
    def __init__(self, body_len: int):
        self.body_len = body_len


class MaxBodySizeValidator:
    def __init__(self, max_size: int):
        self.body_len = 0
        self.max_size = max_size

    def __call__(self, chunk: bytes):
        self.body_len += len(chunk)
        if self.body_len > self.max_size:
            raise MaxBodySizeException(self.body_len)


@app.post("/api/upload/{uuid}")
async def upload_file(
    request: Request,
    uuid: str,
    background_tasks: BackgroundTasks,
):
    max_file_size = 1024 * 1024 * 1024 * settings.max_file_size
    body_validator = MaxBodySizeValidator(max_file_size)
    # TODO: Change this to tmp folder
    uuid = str(uuid4())
    temp_folder = Path(tempfile.mkdtemp())
    logger.debug(f"Temp folder {temp_folder} created")
    file_path = Path(temp_folder, uuid)
    file_target = FileTarget(
        str(file_path), validator=MaxSizeValidator(max_file_size))
    cover_path = Path(temp_folder, str(uuid4()))
    cover_target = FileTarget(
        str(cover_path), validator=MaxSizeValidator(max_file_size))
    show_target = ValueTarget()
    producer_target = ValueTarget()
    title_target = ValueTarget()
    description_target = ValueTarget()
    planned_broadcast_target = ValueTarget()
    comment_target = ValueTarget()
    legacy_url_used_target = ValueTarget()
    try:
        parser = StreamingFormDataParser(headers=request.headers)
        parser.register("file", file_target)
        parser.register("cover", cover_target)
        parser.register("show", show_target)
        parser.register("producer", producer_target)
        parser.register("title", title_target)
        parser.register("description", description_target)
        parser.register("datetime", planned_broadcast_target)
        parser.register("comment", comment_target)
        parser.register("legacy_url_used", legacy_url_used_target)
        async for chunk in request.stream():
            body_validator(chunk)
            parser.data_received(chunk)
    except ClientDisconnect:
        print("Client disconnected")  # TODO: Appropriate handling and logging.
    except MaxBodySizeException as e:
        raise HTTPException(
            status_code=413, detail=f"File to big, allowed {max_file_size} bytes, received {e.body_len}")
    except ValidationError:
        raise HTTPException(
            status_code=413, detail=f"Max file size ({max_file_size} bytes) exceeded")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"error while file upload, {e}")
    if not file_target.multipart_filename:
        raise HTTPException(
            status_code=422, detail="File/multipart name for audio file missing")
    file_path_with_extension = file_path.with_suffix(
        Path(file_target.multipart_filename).suffix)
    file_path.rename(file_path_with_extension)
    file_path = file_path_with_extension

    if cover_target.multipart_filename is not None:
        cover_path_with_extension = cover_path.with_suffix(
            Path(cover_target.multipart_filename).suffix)
        cover_path.rename(cover_path_with_extension)
        cover_path = cover_path_with_extension
    else:
        cover_path = None
    try:
        planned_broadcast_at = datetime.datetime.fromisoformat(
            planned_broadcast_target.value.decode(),
        )
        # Interpret the given datetime in the configured timezone.
        planned_broadcast_at = planned_broadcast_at.replace(
            tzinfo=ZoneInfo(settings.time_zone),
        )
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"'{planned_broadcast_target.value.decode()}' couldn't be parsed as datetime, {e}")
    comment = comment_target.value.decode()
    if comment == "":
        comment = None
    legacy_url_used = legacy_url_used_target.value.decode() == "true"

    uploader_rsl = await BaserowPerson.by_uuid(producer_target.value.decode())
    uploader = uploader_rsl.one()
    show_rsl = await BaserowShow.by_id(int(show_target.value.decode()))
    show = show_rsl.one()
    new_upload = BaserowUpload(
        row_id=-1,
        name=title_target.value.decode(),
        uploader=TableLinkField([uploader.row_link()]),
        show=TableLinkField([show.row_link()]),
        description=description_target.value.decode(),
        planned_broadcast_at=planned_broadcast_at,
        comment_producer=comment,
        state=UploadStates.all_pending_with_legacy_url_state(
            legacy_url_used,
        ).to_multiple_select_field(),
    )
    upload = new_upload.create()
    worker = FileWorker(file_path, cover_path, temp_folder, upload)
    mail = Mail.from_settings()
    background_tasks.add_task(worker.upload_raw)
    background_tasks.add_task(worker.upload_cover)
    background_tasks.add_task(worker.generate_waveform)
    background_tasks.add_task(worker.optimize_file)
    background_tasks.add_task(worker.delete_temp_folder_on_completion)
    background_tasks.add_task(mail.send_on_upload_internal, upload)
    background_tasks.add_task(mail.send_on_upload_external, upload)
    background_tasks.add_task(mail.send_on_upload_supervisor, upload)
    return {
        "success": True,
    }
