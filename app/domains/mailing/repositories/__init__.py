from app.domains.mailing.repositories.batch import MessagesBatchRepository
from app.domains.mailing.repositories.mailing import MailingRepository
from app.domains.mailing.repositories.message import MessageRepository
from app.domains.mailing.repositories.template import MailingTemplateRepository

__all__ = [
    "MailingRepository",
    "MailingTemplateRepository",
    "MessageRepository",
    "MessagesBatchRepository",
]
