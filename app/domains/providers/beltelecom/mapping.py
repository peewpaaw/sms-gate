from ...mailing.enums import MessageStatus


def map_provider_status_to_mailing_status(provider_status: str) -> MessageStatus:
    submitted_ids = {"1383", "1390", "1391"}
    delivered_ids = {"1384", "1385", "1392", "1386", "1388", "1393", "1394", "1395"}
    undelivered_ids = {"1387", "1396"}
    failed_ids = {"1397", "1401"}

    if provider_status in submitted_ids:
        return MessageStatus.SUBMITTED
    elif provider_status in delivered_ids:
        return MessageStatus.DELIVERED
    elif provider_status in undelivered_ids:
        return MessageStatus.UNDELIVERED
    elif provider_status in failed_ids:
        return MessageStatus.FAILED
    else:
        return MessageStatus.UNKNOWN
