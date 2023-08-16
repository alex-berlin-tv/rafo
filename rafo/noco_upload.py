from pathlib import Path

from nocodb.nocodb import NocoDBProject
from nocodb.infra.requests_client import NocoDBRequestsClient
import requests


class Upload:
    """Upload files to NocoDB."""

    def __init__(
        self,
        url: str,
        api_key: str,
        client: NocoDBRequestsClient,
        project: NocoDBProject,
    ):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.client = client
        self.project = project

    def upload_file(
        self,
        file: Path,
        name: str,
        table: str,
        column: str,
        row: int
    ):
        data = self.__upload(file, table, name, column)
        self.client.table_row_update(
            self.project,
            table,
            row,
            {
                column: [{
                    "path": data["path"],
                    "title": data["title"],
                    "size": data["size"],
                }]
            }
        )

    def __upload(
        self,
        file: Path,
        name: str,
        table: str,
        column: str,
    ) -> dict[str, str]:
        upload_request = requests.request(
            "POST",
            f"{self.url}/api/v1/db/storage/upload",
            headers={
                "xc-token": self.api_key,
            },
            data={
                "path": f"{self.project.org_name}/{self.project.project_name}/{table}/{column}",
                "title": name,
            },
            files={
                "file": open(file, "rb")
            }
        )
        return upload_request.json()[0]
