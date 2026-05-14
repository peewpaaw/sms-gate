SEND_EXCHANGE = "mailing.send.x"
SEND_QUEUE = "mailing.send.q"
SEND_RETRY_QUEUE = "mailing.send.retry.q"
SEND_DLQ = "mailing.send.dlq"

STATUS_EXCHANGE = "mailing.status.x"
STATUS_QUEUE = "mailing.status.q"
STATUS_RETRY_QUEUE = "mailing.status.retry.q"
STATUS_DLQ = "mailing.status.dlq"

SEND_BATCH_ROUTING_KEY = "mailing.send"
SEND_RETRY_ROUTING_KEY = "mailing.send.retry"
STATUS_CHECK_ROUTING_KEY = "mailing.status"
STATUS_RETRY_ROUTING_KEY = "mailing.status.retry"
DEAD_ROUTING_KEY = "mailing.dead"

RETRY_TTL_MS = 30_000
