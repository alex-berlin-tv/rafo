from .config import settings
from .file_worker import FileWorker
from .log import logger
from .mail import Mail
from .model import NocoEpisodeNew, ProducerUploadData

import datetime
from uuid import uuid4
from pathlib import Path
import tempfile

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nocodb.exceptions import NocoDBAPIError
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, ValueTarget
from streaming_form_data.validators import MaxSizeValidator, ValidationError

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html.jinja2", {"request": request})


@app.get("/help")
async def help(request: Request):
    return templates.TemplateResponse("help.html.jinja2", {"request": request})


@app.get("/upload/{uuid}")
async def upload(
    request: Request,
    uuid: str,
):
    data = {
        "request": request,
        "producer_uuid": uuid,
        "base_url": settings.base_url,
    }
    return templates.TemplateResponse("upload.html.jinja2", data)


@app.get("/api/producer_for_upload/{uuid}")
async def producer_for_upload_info(
    uuid: str,
):
    try:
        data = ProducerUploadData.from_nocodb(uuid)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Unter dieser URL kann kein Formular gefunden werden. Stelle bitte sicher, dass du den Link korrekt kopiert hast und probiere es nochmals.")
    except NocoDBAPIError as e:
        # TODO: Log this
        raise HTTPException(
            status_code=500,
            detail=f"NocoDBAPIError. Message: {e}. Response Text: {e.response_text}",
        )
    return data


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
    max_file_size = 1024 * 1024 * 1024 * settings.max_file_size  # type: ignore
    body_validator = MaxBodySizeValidator(max_file_size)
    # TODO: Change this to tmp folder
    uuid = str(uuid4())
    temp_folder = Path(tempfile.mkdtemp())
    logger.debug(f"Temp folder {temp_folder} created")
    file_path = Path(temp_folder, uuid)
    file_target = FileTarget(
        str(file_path), validator=MaxSizeValidator(max_file_size))
    show_target = ValueTarget()
    producer_target = ValueTarget()
    title_target = ValueTarget()
    description_target = ValueTarget()
    planned_broadcast_target = ValueTarget()
    comment_target = ValueTarget()
    try:
        parser = StreamingFormDataParser(headers=request.headers)
        parser.register("file", file_target)
        parser.register("show", show_target)
        parser.register("producer", producer_target)
        parser.register("title", title_target)
        parser.register("description", description_target)
        parser.register("datetime", planned_broadcast_target)
        parser.register("comment", comment_target)
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
            status_code=422, detail="File/multipart filename missing")
    path_with_extension = file_path.with_suffix(Path(file_target.multipart_filename).suffix)
    file_path.rename(path_with_extension)
    file_path = path_with_extension
    try:
        planned_broadcast_at = datetime.datetime.strptime(
            planned_broadcast_target.value.decode(),
            "%Y-%m-%dT%H:%M",
        )
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"'{planned_broadcast_target.value.decode()}' couldn't be parsed as datetime, {e}")
    comment = comment_target.value.decode()
    if comment == "":
        comment = None
    episode = NocoEpisodeNew(  # type: ignore
        title=title_target.value.decode(),  # type: ignore
        uuid=uuid,  # type: ignore
        description=description_target.value.decode(),  # type: ignore
        planned_broadcast_at=planned_broadcast_at.strftime("%Y-%m-%d %H:%M:%S%z"),  # type: ignore
        comment=comment_target.value.decode(),  # type: ignore
    )
    episode_id = episode.add_to_noco(producer_target.value.decode(), show_target.value.decode())
    worker = FileWorker(file_path, temp_folder, episode_id)
    mail = Mail.from_settings()
    background_tasks.add_task(worker.upload_raw)
    background_tasks.add_task(worker.generate_waveform)
    background_tasks.add_task(worker.optimize_file)
    background_tasks.add_task(worker.delete_temp_folder_on_completion)
    background_tasks.add_task(mail.send_on_upload_internal, episode_id)
    background_tasks.add_task(mail.send_on_upload_external, episode_id)
    return {
        "success": True,
    }