from app.domains.mailing.schemas.batch import MessagesBatchRead, SendBatchTask
from app.domains.mailing.schemas.mailing import (
    MailingCreate,
    MailingRead,
    MailingUpdate,
    MessageCreate,
    MessageRead,
    MessageUpdate,
)
from app.domains.mailing.schemas.sms_analyze import (
    SmsTextAnalyzeRequest,
    SmsTextAnalyzeResponse,
)
from app.domains.mailing.schemas.template import (
    MailingTemplateCreate,
    MailingTemplateRead,
    MailingTemplateUpdate,
)

__all__ = [
    "MailingCreate",
    "MailingRead",
    "MailingTemplateCreate",
    "MailingTemplateRead",
    "MailingTemplateUpdate",
    "MailingUpdate",
    "MessageCreate",
    "MessageRead",
    "MessageUpdate",
    "MessagesBatchRead",
    "SendBatchTask",
    "SmsTextAnalyzeRequest",
    "SmsTextAnalyzeResponse",
]
