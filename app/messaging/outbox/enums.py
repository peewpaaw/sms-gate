from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class OutboxEventType(StrEnum):
    SEND_BATCH = "mailing.send"
    CHECK_STATUS = "mailing.status"
