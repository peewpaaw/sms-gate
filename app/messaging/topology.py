MAILING_EXCHANGE = "mailing.x"

SEND_BATCH_QUEUE = "mailing.send.q"
SEND_BATCH_RETRY_QUEUE = "mailing.send.retry.q"
SEND_BATCH_DLQ = "mailing.send.dlq"

STATUS_QUEUE = "mailing.status.q"
STATUS_RETRY_QUEUE = "mailing.status.retry.q"
STATUS_DLQ = "mailing.status.dlq"

SEND_BATCH_ROUTING_KEY = "mailing.send"
SEND_BATCH_RETRY_ROUTING_KEY = "mailing.send.retry"
STATUS_ROUTING_KEY = "mailing.status"
STATUS_RETRY_ROUTING_KEY = "mailing.status.retry"

SEND_BATCH_DEAD_ROUTING_KEY = "mailing.send.dead"
STATUS_DEAD_ROUTING_KEY = "mailing.status.dead"

RETRY_TTL_MS = 30_000
