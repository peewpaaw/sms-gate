# sms-gate

Async SMS Gateway MVP: FastAPI API, PostgreSQL source of truth, RabbitMQ queues,
aio-pika workers, provider adapter abstraction and idempotent mailing creation.

## Local Run

```bash
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload
```

Workers:

```bash
python -m app.workers.send
python -m app.workers.status
```

Tests:

```bash
pytest
ruff check .
```

Default local API keys:

- UI user: `X-API-Key: local-ui-key`
- ERP technical user: `X-API-Key: local-erp-key`

Create a mailing:

```bash
curl -X POST http://localhost:8000/sms/mailings \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: local-ui-key' \
  -H 'Idempotency-Key: demo-1' \
  -d '{
    "provider_code": "fake",
    "sender": "ACME",
    "messages": [{"msisdn": "375447222120", "text": "hello"}]
  }'
```