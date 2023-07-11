from ..config import settings
from ..model import NocoEpisode

from email.message import EmailMessage
import smtplib
import ssl

import jinja2


class Mail:
    """Handles the sending of mails."""

    def __init__(
        self,
        sender_address: str,
        host: str,
        user: str,
        password: str,
        port: int,
    ):
        self.sender_address = sender_address
        self.host = host
        self.user = user
        self.password = password
        self.port = port

    @classmethod
    def from_settings(cls):
        return cls(
            settings.smtp_sender_address,  # type: ignore
            settings.smtp_host,  # type: ignore
            settings.smtp_user,  # type: ignore
            settings.smtp_password,  # type: ignore
            settings.smtp_port,  # type: ignore
        )

    def send(self, recipient: str, subject: str, message: str):
        msg = EmailMessage()
        msg.set_content(message)
        msg["Subject"] = subject
        msg["From"] = self.sender_address
        msg["To"] = recipient
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
            server.login(self.user, self.password)
            server.send_message(msg)

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
        message = self.__get_template("new_upload_internal.txt.jinja2").render(
            episode=episode,
            producer=producer,
            show=show,
            dev_mode=settings.dev_mode, # type: ignore
        )
        self.send(
            settings.on_upload_mail, # type: ignore
            f"e-{episode.noco_id:04d}: Neuer Upload {show.name}",
            message
        )

    def send_on_upload_external(
        self,
        episode_id: int,
    ):
        episode = NocoEpisode.from_nocodb_by_id(episode_id)
        producer = episode.get_producer()
        show = episode.get_show()
        message = self.__get_template("new_upload_producer.txt.jinja2").render(
            episode=episode,
            producer=producer,
            show=show,
            dev_mode=settings.dev_mode, # type: ignore
            contact_mail=settings.contact_mail, # type: ignore
        )
        self.send(
            producer.email,
            "Sendung erfolgreich hochgeladen",
            message,
        )

    @staticmethod
    def __get_template(name: str) -> jinja2.Template:
        loader = jinja2.PackageLoader(__name__, "")
        env = jinja2.Environment(loader=loader)
        return env.get_template(name)