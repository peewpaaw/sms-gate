from enum import StrEnum


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_cls]


class UserRole(StrEnum):
    UI = "ui"
    ERP = "erp"


class MailingSource(StrEnum):
    UI = "ui"
    ERP = "erp"


class MailingStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIALLY_SUBMITTED = "partially_submitted"
    SUBMITTED = "submitted"
    PARTIALLY_DELIVERED = "partially_delivered"
    DELIVERED = "delivered"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SmsMessageStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SENDING = "sending"
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SmsBatchStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SENDING = "sending"
    SUBMITTED = "submitted"
    STATUS_PENDING = "status_pending"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


class ProviderDispatchStatus(StrEnum):
    CREATED = "created"
    SENT_TO_PROVIDER = "sent_to_provider"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TEMPORARY_ERROR = "temporary_error"
    PERMANENT_ERROR = "permanent_error"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"
