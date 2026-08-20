from enum import StrEnum


class MailingStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"


class MessageStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SmsMessageEncoding(StrEnum):
    GSM7 = "gsm7"
    UCS2 = "ucs2"


class MessagesBatchStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SENDING = "sending"
    SUBMITTED = "submitted"
    PARTIALLY_SUBMITTED = "partially_submitted"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"
