from ..config import settings
from ..model import BaserowPerson, BaserowUpload

import emails
import jinja2


class Mail:
    """Handles the sending of mails."""

    def __init__(
        self,
        sender_address: str,
        sender_name: str,
        host: str,
        user: str,
        password: str,
        port: int,
    ):
        self.sender_address = sender_address
        self.sender_name = sender_name
        self.host = host
        self.user = user
        self.password = password
        self.port = port

    @classmethod
    def from_settings(cls):
        return cls(
            settings.smtp_sender_address,
            settings.on_upload_sender_name,
            settings.smtp_host,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_port,
        )

    def send(self, recipient: str, subject: str, html: str, plain: str):
        msg = emails.Message(
            subject=subject,
            html=html,
            text=plain,
            mail_from=(self.sender_name, self.sender_address),
        )
        msg.send(
            to=recipient,
            smtp={
                "host": self.host,
                "port": self.port,
                "ssl": True,
                "user": self.user,
                "password": self.password,
            }
        )

    def send_upload_link(self, recipient: str, producer: str):
        raise NotImplemented()
        message = self.__get_template("uploadlink.txt.jinja2").render(
            producer=producer,
        )
        self.send(recipient, "Dein Radio-Uploadlink", message)

    def send_on_upload_internal(self, upload: BaserowUpload):
        uploader = upload.get_uploader()
        show = upload.get_show()
        data = {
            "episode": upload,
            "producer": uploader,
            "show": show,
            "dev_mode": settings.dev_mode,
        }
        plain = self.__get_template(
            "new_upload_internal.txt.jinja2").render(data)
        html = self.__get_template(
            "new_upload_internal.html.jinja2").render(data)
        self.send(
            settings.on_upload_mail,
            f"{self.__test()}u-{upload.row_id:05d}: Neuer Upload {show.name}",
            html,
            plain,
        )

    def send_on_upload_external(self, upload: BaserowUpload):
        uploader = upload.get_uploader()
        show = upload.get_show()
        data = {
            "episode": upload,
            "producer": uploader,
            "show": show,
            "dev_mode": settings.dev_mode,
            "contact_mail": settings.contact_mail,
        }
        plain = self.__get_template(
            "new_upload_producer.txt.jinja2").render(data)
        html = self.__get_template(
            "new_upload_producer.html.jinja2").render(data)
        self.send(
            uploader.email,
            f"{self.__test()}Sendung erfolgreich hochgeladen",
            html,
            plain,
        )

    def send_on_upload_supervisor(self, upload: BaserowUpload):
        show = upload.get_show()
        supervisors = show.get_supervisors()
        # supervisors = BaserowPerson.by_link_field(show.supervisors).any()
        if len(supervisors) == 0:
            return
        uploader = upload.get_uploader()
        data = {
            "episode": upload,
            "producer": uploader,
            "show": show,
            "dev_mode": settings.dev_mode,
            "contact_mail": settings.contact_mail,
        }
        plain = self.__get_template(
            "new_upload_supervisor.txt.jinja2").render(data)
        html = self.__get_template(
            "new_upload_supervisor.html.jinja2").render(data)
        for supervisor in supervisors:
            self.send(
                supervisor.email,
                f"{self.__test()}u-{upload.row_id:05d}: Neuer Upload {show.name}",
                html,
                plain,
            )

    def __test(self) -> str:
        """
        Returns `[Test] ` if development mode is enabled. Used in the subject line
        of notification emails.
        """
        if not settings.dev_mode:
            return ""
        return "[Test] "

    @staticmethod
    def __get_template(name: str) -> jinja2.Template:
        loader = jinja2.PackageLoader(__name__, "")
        env = jinja2.Environment(loader=loader)
        return env.get_template(name)
