# Отчет По Реализации SMS Gateway MVP

## Краткий Результат

Реализован базовый SMS Gateway MVP по плану: FastAPI API, async SQLAlchemy/Alembic,
PostgreSQL как source of truth, RabbitMQ topology/publisher, aio-pika workers,
provider abstraction, fake provider adapter, idempotent mailing creation, API-key user
model, тесты и локальная документация запуска.

План-файл не изменялся.

## Поэтапность Работ

### Этап 0: Каркас Проекта

Что сделано:

- Исправлена структура Python package: добавлен `app/__init__.py`.
- Опечаточный файл `app/core/__init__py.py` заменен на `app/core/__init__.py`.
- Обновлен `pyproject.toml`: зависимости backend/runtime/dev, ruff, pytest config,
  setuptools package discovery.
- Заполнен `docker-compose.yml` для PostgreSQL и RabbitMQ Management.
- Добавлены базовые настройки и structured logging.
- `app/main.py` переведен с hello-world endpoints на FastAPI app с routers.
- Добавлен `/health`.

Основные файлы:

- `pyproject.toml`
- `docker-compose.yml`
- `app/main.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/api/routes/health.py`

### Этап 1: БД, Модели, Alembic

Что сделано:

- Добавлен async SQLAlchemy engine/session.
- Добавлен Alembic async setup.
- Добавлены enum-ы статусов и доменные ORM-модели.
- Добавлена первая миграция с таблицами:
  `users`, `providers`, `mailings`, `sms_messages`, `sms_batches`,
  `provider_dispatches`, `status_checks`, `idempotency_keys`.
- В `sms_messages` добавлен `provider_custom_id` длиной до 20 символов под лимит
  первого провайдера.
- В миграции добавлен seed provider `fake`.

Основные файлы:

- `app/db/base.py`
- `app/db/session.py`
- `app/models/enums.py`
- `app/models/user.py`
- `app/models/provider.py`
- `app/models/mailing.py`
- `app/models/sms_message.py`
- `app/models/sms_batch.py`
- `app/models/provider_dispatch.py`
- `app/models/status_check.py`
- `app/models/idempotency_key.py`
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260511_0001_initial_schema.py`

### Этап 2: Provider Registry И Fake Adapter

Что сделано:

- Добавлен внутренний provider protocol.
- Добавлены DTO: `ProviderBatch`, `ProviderMessage`, `ProviderSendResult`,
  `ProviderMessageSendResult`, `ProviderStatusResult`.
- Добавлен registry провайдеров по `code`.
- Добавлен `FakeSmsProviderAdapter` для локального dev/test flow.
- Добавлен seed fallback для provider `fake`.

Основные файлы:

- `app/providers/base.py`
- `app/providers/fake.py`
- `app/providers/registry.py`
- `app/services/seeding.py`

### Этап 3: API Создания И Чтения Mailing

Что сделано:

- Добавлены Pydantic schemas для mailing/messages/providers.
- Реализован `POST /sms/mailings`.
- Реализованы endpoints чтения:
  `GET /sms/mailings`, `GET /sms/mailings/{mailing_id}`,
  `GET /sms/mailings/{mailing_id}/messages`,
  `GET /sms/messages`, `GET /sms/messages/{message_id}`,
  `GET /providers`.
- Создание mailing выполняется в DB transaction:
  provider validation, reject `provider_code = "auto"`, create mailing,
  create messages, create batches.
- Одиночное SMS создается как mailing с одним `sms_message`.
- Добавлен batch splitting по `provider.max_batch_size`.

Основные файлы:

- `app/api/routes/mailings.py`
- `app/api/routes/messages.py`
- `app/api/routes/providers.py`
- `app/schemas/mailing.py`
- `app/schemas/provider.py`
- `app/services/mailing.py`

### Этап 4: RabbitMQ Topology И Publisher

Что сделано:

- Описана topology:
  `sms.send.x`, `sms.send.q`, `sms.send.retry.q`, `sms.send.dlq`,
  `sms.status.x`, `sms.status.q`, `sms.status.retry.q`, `sms.status.dlq`.
- Добавлены routing keys:
  `sms.send.batch`, `sms.send.retry`, `sms.status.check`,
  `sms.status.retry`, `sms.dead`.
- Реализованы aio-pika connection/topology setup.
- Реализованы publishers для send/status tasks.
- Payload задач содержит идентификаторы, а не полный SMS payload.

Основные файлы:

- `app/messaging/topology.py`
- `app/messaging/rabbitmq.py`
- `app/messaging/publisher.py`
- `app/messaging/schemas.py`

### Этап 5: Send Worker

Что сделано:

- Добавлен consumer `sms.send.q`.
- Worker загружает batch/messages из БД.
- Добавлена идемпотентная проверка: уже отправленные сообщения не отправляются повторно.
- Worker вызывает provider adapter.
- Результат сохраняется в `provider_dispatches`.
- Обновляются `sms_messages.provider_message_id`, статусы сообщений и batch.
- Ack выполняется через `message.process()` после успешной обработки.
- Добавлена retry ветка для temporary provider errors.
- Добавлена dead-letter/final failed логика при exhausted retries.

Основные файлы:

- `app/workers/send.py`
- `app/providers/base.py`
- `app/providers/fake.py`
- `app/models/provider_dispatch.py`

### Этап 6: Status Worker И Агрегация Статусов

Что сделано:

- После successful submit публикуются status check tasks.
- Добавлен consumer `sms.status.q`.
- Worker вызывает provider status API.
- Результат сохраняется в `status_checks`.
- Обновляются статусы `sms_messages`, `sms_batches`, `mailings`.
- Добавлена функция агрегации mailing status из статусов сообщений.
- Добавлена retry ветка для transient status errors.

Основные файлы:

- `app/workers/status.py`
- `app/services/statuses.py`
- `app/models/status_check.py`

### Этап 7: Idempotency И User/Auth MVP

Что сделано:

- Добавлен простой API-key auth через `X-API-Key`.
- Добавлены локальные ключи:
  `local-ui-key` для UI user и `local-erp-key` для ERP technical user.
- Пользователь создается lazy при первом запросе с локальным ключом.
- Добавлен `source`: `ui` или `erp`.
- Добавлен `created_by` ownership.
- Чтение mailings/messages ограничено текущим пользователем.
- Реализован `Idempotency-Key`:
  request hash, stored response, replay duplicate response,
  conflict при повторе ключа с другим body.

Основные файлы:

- `app/api/deps.py`
- `app/services/security.py`
- `app/services/idempotency.py`
- `app/models/user.py`
- `app/models/idempotency_key.py`

### Этап 8: Тесты И Наблюдаемость

Что сделано:

- Добавлены тесты на:
  создание mailing,
  single SMS как mailing,
  batch splitting,
  provider custom id limit,
  provider response mapping,
  mailing status aggregation.
- Добавлен JSON structured logging.
- Обновлен `README.md` с командами запуска API, workers, tests.
- Создан локальный `.venv` для проверки.
- Прогнаны lint и tests.

Основные файлы:

- `tests/conftest.py`
- `tests/test_mailing_service.py`
- `tests/test_provider_fake.py`
- `app/core/logging.py`
- `README.md`

## Карта Каталогов

### `app/`

Основной Python package приложения.

### `app/api/`

HTTP слой FastAPI.

- `app/api/deps.py` - dependency injection: DB session, current user/API-key auth.
- `app/api/routes/health.py` - health endpoint.
- `app/api/routes/mailings.py` - endpoints рассылок.
- `app/api/routes/messages.py` - endpoints SMS-сообщений.
- `app/api/routes/providers.py` - список доступных провайдеров.

### `app/core/`

Базовая инфраструктура приложения.

- `app/core/config.py` - typed settings через Pydantic Settings.
- `app/core/logging.py` - JSON structured logging.

### `app/db/`

SQLAlchemy инфраструктура.

- `app/db/base.py` - declarative base и mixins.
- `app/db/session.py` - async engine/session factory и FastAPI dependency.

### `app/models/`

Persisted domain state.

- `app/models/enums.py` - enum-ы ролей и статусов.
- `app/models/user.py` - UI/ERP users.
- `app/models/provider.py` - provider config.
- `app/models/mailing.py` - верхнеуровневая рассылка.
- `app/models/sms_message.py` - отдельное SMS.
- `app/models/sms_batch.py` - batch сообщений под provider limit.
- `app/models/provider_dispatch.py` - попытки отправки провайдеру.
- `app/models/status_check.py` - история polling статусов.
- `app/models/idempotency_key.py` - API idempotency records.

### `app/schemas/`

Pydantic API contracts.

- `app/schemas/mailing.py` - request/response схемы mailings/messages.
- `app/schemas/provider.py` - response schema providers.

### `app/services/`

Бизнес-логика приложения.

- `app/services/mailing.py` - создание mailing, batch splitting, provider validation.
- `app/services/idempotency.py` - idempotent create flow.
- `app/services/security.py` - API-key hashing.
- `app/services/seeding.py` - local seed/fallback для fake provider.
- `app/services/statuses.py` - aggregate mailing status logic.

### `app/providers/`

Интеграционный слой SMS providers.

- `app/providers/base.py` - protocol, DTO, provider errors.
- `app/providers/fake.py` - fake provider adapter.
- `app/providers/registry.py` - registry adapter-ов по provider code.

### `app/messaging/`

RabbitMQ слой.

- `app/messaging/topology.py` - exchanges, queues, routing keys.
- `app/messaging/rabbitmq.py` - aio-pika connection и topology declaration.
- `app/messaging/publisher.py` - publish send/status tasks.
- `app/messaging/schemas.py` - payload schemas для RabbitMQ tasks.

### `app/workers/`

Фоновые consumers.

- `app/workers/send.py` - отправка batch-ей провайдеру.
- `app/workers/status.py` - polling статусов у провайдера.

### `alembic/`

Миграции БД.

- `alembic/env.py` - async Alembic environment.
- `alembic/script.py.mako` - migration template.
- `alembic/versions/20260511_0001_initial_schema.py` - первая миграция схемы.

### `tests/`

Автотесты.

- `tests/conftest.py` - async SQLite test session.
- `tests/test_mailing_service.py` - mailing/domain tests.
- `tests/test_provider_fake.py` - fake provider mapping tests.

## Проверки

Выполнено:

```bash
.venv/bin/ruff check .
.venv/bin/python -m pytest
```

Результат:

- Ruff: `All checks passed`.
- Pytest: `5 passed`.

## Важные Технические Замечания

- Реальный SMS provider пока не реализован, вместо него используется `fake` adapter.
  Это осознанно: без credentials и точного внешнего API-контракта лучше не выдумывать
  production-интеграцию.
- Python target изменен с `>=3.14` на `>=3.12,<3.15`, чтобы проект оставался
  совместимым с текущей FastAPI/SQLAlchemy экосистемой.
- RabbitMQ publisher сейчас логирует warning, если RabbitMQ недоступен. Для production
  стоит заменить это на outbox pattern, чтобы публикация задач была атомарна с DB commit.
- Auth сделан как MVP API-key слой. Для production потребуется нормальная модель
  управления ключами/секретами и, возможно, JWT/OAuth для UI.
