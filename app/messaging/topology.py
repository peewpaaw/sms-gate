SEND_EXCHANGE = "sms.send.x"
SEND_QUEUE = "sms.send.q"
SEND_RETRY_QUEUE = "sms.send.retry.q"
SEND_DLQ = "sms.send.dlq"

STATUS_EXCHANGE = "sms.status.x"
STATUS_QUEUE = "sms.status.q"
STATUS_RETRY_QUEUE = "sms.status.retry.q"
STATUS_DLQ = "sms.status.dlq"

SEND_BATCH_ROUTING_KEY = "sms.send.batch"
SEND_RETRY_ROUTING_KEY = "sms.send.retry"
STATUS_CHECK_ROUTING_KEY = "sms.status.check"
STATUS_RETRY_ROUTING_KEY = "sms.status.retry"
DEAD_ROUTING_KEY = "sms.dead"

RETRY_TTL_MS = 30_000
