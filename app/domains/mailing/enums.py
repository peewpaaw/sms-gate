from enum import StrEnum


class MailingStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"


class MessageStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"
    UNKNOWN = "unknown"


class MessagesBatchStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "sent"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"
