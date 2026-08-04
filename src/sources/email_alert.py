"""Email-alert adapter — reads job-site alert emails from an IMAP mailbox."""

from domain.offer import Offer
from sources.base import Adapter


class EmailAlert(Adapter):
    name = "email-alert"
    basis = "email_alert"

    def __init__(self, host: str, login: str, password: str, folder: str = "Alerts") -> None:
        self.config = (host, login, password, folder)

    async def fetch(self) -> list[Offer]:
        raise NotImplementedError
