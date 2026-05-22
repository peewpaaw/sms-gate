from enum import StrEnum


class MailingStatus(StrEnum):
    CREATED = "created"
    PREPARED = "prepared"
    QUEUED = "queued"
    SUBMITTED = "submitted"


class MessageStatus(StrEnum):
    CREATED = "created"
    PREPARED = "prepared"
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
    PARTIALLY_SUBMITTED = "partially_submitted"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


class MailingOutboxEventType(StrEnum):
    SEND_BATCH = "mailing.send"


class MailingOutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
