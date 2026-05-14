from enum import StrEnum


class MailingStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"


class MessageStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    SENDING = "sending"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"
    UNKNOWN = "unknown"
