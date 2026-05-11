from collections import Counter

from app.models.enums import MailingStatus, SmsMessageStatus


def aggregate_mailing_status(statuses: list[SmsMessageStatus]) -> MailingStatus:
    if not statuses:
        return MailingStatus.CREATED

    counts = Counter(statuses)
    total = len(statuses)

    if counts[SmsMessageStatus.DELIVERED] == total:
        return MailingStatus.DELIVERED
    if counts[SmsMessageStatus.FAILED] + counts[SmsMessageStatus.UNDELIVERED] == total:
        return MailingStatus.FAILED
    if counts[SmsMessageStatus.SUBMITTED] == total:
        return MailingStatus.SUBMITTED
    if counts[SmsMessageStatus.QUEUED] == total:
        return MailingStatus.QUEUED
    if counts[SmsMessageStatus.SENDING] > 0:
        return MailingStatus.PROCESSING
    if counts[SmsMessageStatus.DELIVERED] > 0:
        return MailingStatus.PARTIALLY_DELIVERED
    if counts[SmsMessageStatus.FAILED] > 0 or counts[SmsMessageStatus.UNDELIVERED] > 0:
        return MailingStatus.PARTIALLY_FAILED
    if counts[SmsMessageStatus.SUBMITTED] > 0:
        return MailingStatus.PARTIALLY_SUBMITTED
    return MailingStatus.PROCESSING
