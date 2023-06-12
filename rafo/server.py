from model import ProducerUploadData

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("index.html.jinja2", {"request": request})


@app.get("/help")
def help(request: Request):
    return templates.TemplateResponse("help.html.jinja2", {"request": request})


@app.get("/upload/{uuid}")
def upload(
    request: Request,
    uuid: str,
):
    data = {
        "request": request,
        "producer_uuid": uuid,
    }
    return templates.TemplateResponse("upload.html.jinja2", data)


@app.get("/api/producer_for_upload/{uuid}")
def producer_for_upload_info(
    uuid: str,
):
    try:
        data = ProducerUploadData.from_nocodb(uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unter dieser URL kann kein Formular gefunden werden. Stelle bitte sicher, dass du den Link korrekt kopiert hast und probiere es nochmals.")
    return data