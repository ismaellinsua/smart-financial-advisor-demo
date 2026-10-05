"""Sending email through any SMTP server (Gmail with an app password is free and enough to start).

Configuration (Streamlit secrets for the app, GitHub secrets for scheduled jobs; environment variables also work):
    smtp_host       e.g. smtp.gmail.com
    smtp_port       587 (STARTTLS, default) or 465 (TLS)
    smtp_user       the account, e.g. nirkana.oficial@gmail.com
    smtp_password   for Gmail, an «app password» (Google account → Security → App passwords)
    smtp_from       optional sender shown, e.g. "NirKanA <nirkana.oficial@gmail.com>"
Nothing is sent while smtp_host, smtp_user and smtp_password are not all set.
"""

import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class MailNotConfigured(RuntimeError):
    """Raised when sending is attempted without SMTP settings."""


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.fullmatch(str(value or "").strip()))


def mask_email(value: str) -> str:
    """n***@gmail.com: enough to recognise one's own address without revealing it."""
    user, _, domain = str(value or "").partition("@")
    return f"{user[:1]}***@{domain}" if user and domain else "***"


class Mailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str = ""):
        self.host, self.port, self.user, self.password = host, int(port or 587), user, password
        self.sender = sender or formataddr(("NirKanA", user))

    @classmethod
    def from_settings(cls, get=None) -> "Mailer | None":
        """From a lookup function (e.g. Streamlit secrets) or the environment; None when not configured."""
        def value(name: str) -> str:
            found = get(name) if get else None
            return str(found or os.environ.get(name.upper(), "") or "").strip()

        host, user, password = value("smtp_host"), value("smtp_user"), value("smtp_password")
        if not (host and user and password):
            return None
        return cls(host, int(value("smtp_port") or 587), user, password, value("smtp_from"))

    def message(self, to: str, subject: str, text: str, html: str = "",
                attachments: list[tuple[str, bytes, str]] = (), reply_to: str = "") -> EmailMessage:
        if not valid_email(to):
            raise ValueError("Dirección de email no válida.")
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to.strip()
        msg["Subject"] = subject.replace("\n", " ")[:200]
        # A business's customers reply to the business, not to the sending account.
        msg["Reply-To"] = reply_to.strip() if valid_email(reply_to) else parseaddr(self.sender)[1] or self.user
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        for name, data, mime in attachments:
            maintype, _, subtype = mime.partition("/")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
        return msg

    def send(self, to: str, subject: str, text: str, html: str = "",
             attachments: list[tuple[str, bytes, str]] = (), reply_to: str = "") -> None:
        msg = self.message(to, subject, text, html, attachments, reply_to)
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=30) as server:
                server.login(self.user, self.password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.starttls(context=context)
                server.login(self.user, self.password)
                server.send_message(msg)
