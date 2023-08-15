from ..config import settings
from ..model import NocoEpisode

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import ssl

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

    def send_on_upload_internal(
        self,
        episode_id: int,
    ):
        episode = NocoEpisode.from_nocodb_by_id(episode_id)
        producer = episode.get_producer()
        show = episode.get_show()
        data = {
            "episode": episode,
            "producer": producer,
            "show": show,
            "dev_mode": settings.dev_mode,
        }
        plain = self.__get_template("new_upload_internal.txt.jinja2").render(data)
        html = self.__get_template("new_upload_internal.html.jinja2").render(data)
        self.send(
            settings.on_upload_mail,
            f"e-{episode.noco_id:04d}: Neuer Upload {show.name}",
            html,
            plain,
        )

    def send_on_upload_external(
        self,
        episode_id: int,
    ):
        episode = NocoEpisode.from_nocodb_by_id(episode_id)
        producer = episode.get_producer()
        show = episode.get_show()
        data = {
            "episode": episode,
            "producer": producer,
            "show": show,
            "dev_mode": settings.dev_mode,
            "contact_mail": settings.contact_mail,
        }
        plain = self.__get_template("new_upload_producer.txt.jinja2").render(data)
        html = self.__get_template("new_upload_producer.html.jinja2").render(data)
        self.send(
            producer.email,
            "Sendung erfolgreich hochgeladen",
            html,
            plain,
        )

    @staticmethod
    def __get_template(name: str) -> jinja2.Template:
        loader = jinja2.PackageLoader(__name__, "")
        env = jinja2.Environment(loader=loader)
        return env.get_template(name)