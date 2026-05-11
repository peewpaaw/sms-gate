---
name: sms mvp phases
overview: "Разбить реализацию SMS Gateway MVP на короткие этапы: сначала привести каркас проекта в рабочее состояние, затем добавить БД/миграции, API, RabbitMQ pipeline, provider adapter, workers, идемпотентность и тесты."
todos:
  - id: stage-0-bootstrap
    content: "Этап 0: привести проектный каркас, зависимости, compose и health endpoint в рабочее состояние."
    status: completed
  - id: stage-1-db-alembic
    content: "Этап 1: настроить async SQLAlchemy, Alembic, модели, enum-ы и первую миграцию."
    status: completed
  - id: stage-2-provider-registry
    content: "Этап 2: добавить provider abstraction, registry и базовый/fake adapter."
    status: completed
  - id: stage-3-mailing-api
    content: "Этап 3: реализовать API создания и чтения mailing/messages/providers без реальной отправки."
    status: completed
  - id: stage-4-rabbitmq
    content: "Этап 4: настроить RabbitMQ topology и publisher задач отправки."
    status: completed
  - id: stage-5-send-worker
    content: "Этап 5: реализовать send worker, adapter вызов, dispatch persistence, retry/DLQ."
    status: completed
  - id: stage-6-status-worker
    content: "Этап 6: реализовать status polling worker и агрегацию статусов mailing."
    status: completed
  - id: stage-7-idempotency-auth
    content: "Этап 7: добавить Idempotency-Key и базовую user/auth модель для UI/ERP."
    status: completed
  - id: stage-8-tests-observability
    content: "Этап 8: закрыть критичные тесты, structured logs и README с локальным flow."
    status: completed
isProject: false
---

# Поэтапный План Работ SMS Gateway MVP

## Текущая Точка

В репозитории сейчас минимальный FastAPI hello-world в [`/Users/jslv/Documents/projects/sms-gate/app/main.py`](/Users/jslv/Documents/projects/sms-gate/app/main.py), базовый [`/Users/jslv/Documents/projects/sms-gate/pyproject.toml`](/Users/jslv/Documents/projects/sms-gate/pyproject.toml), пустой [`/Users/jslv/Documents/projects/sms-gate/docker-compose.yml`](/Users/jslv/Documents/projects/sms-gate/docker-compose.yml) и архитектурный план [`/Users/jslv/.cursor/plans/sms_architecture_v2_f10e06d7.plan.md`](/Users/jslv/.cursor/plans/sms_architecture_v2_f10e06d7.plan.md).

Сразу заложим один практичный выбор: делать MVP вертикальными слоями, но не тащить provider polling/retry/idempotency до того, как есть стабильная БД-схема и базовое создание mailing.

## Этап 0: Привести Каркас В Порядок

Цель: получить запускаемый проект с нормальной структурой, настройками и локальной инфраструктурой.

- Исправить опечатку [`/Users/jslv/Documents/projects/sms-gate/app/core/__init__py.py`](/Users/jslv/Documents/projects/sms-gate/app/core/__init__py.py) на `app/core/__init__.py`.
- Привести [`/Users/jslv/Documents/projects/sms-gate/pyproject.toml`](/Users/jslv/Documents/projects/sms-gate/pyproject.toml) к рабочему Python target. Я бы выбрал `>=3.12,<3.15`, потому что `>=3.14` пока даст лишнюю боль с совместимостью зависимостей.
- Добавить зависимости: `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `aio-pika`, `httpx`, `pytest`, `pytest-asyncio`, `ruff`.
- Заполнить [`/Users/jslv/Documents/projects/sms-gate/docker-compose.yml`](/Users/jslv/Documents/projects/sms-gate/docker-compose.yml) PostgreSQL и RabbitMQ management.
- Ввести `app/core/config.py`, `app/core/logging.py`, health endpoint и минимальный README с командами запуска.

Критерий готовности: `uvicorn app.main:app --reload` стартует, `/health` отвечает, Postgres/RabbitMQ поднимаются через compose.

## Этап 1: БД, Модели, Alembic

Цель: зафиксировать source of truth до API и воркеров.

- Настроить async SQLAlchemy engine/session.
- Инициализировать Alembic под async migrations.
- Добавить enum-ы статусов: `MailingStatus`, `SmsMessageStatus`, `SmsBatchStatus`, `ProviderDispatchStatus`.
- Создать модели и первую миграцию: `users`, `providers`, `mailings`, `sms_messages`, `sms_batches`, `sms_batch_messages` или явная связь message-to-batch, `provider_dispatches`, `status_checks`, `idempotency_keys`.
- Для `sms_messages` сразу предусмотреть короткий `provider_custom_id`, потому что в архитектуре указан лимит custom_id 20 символов у первого провайдера.

Критерий готовности: миграции применяются на пустую БД, модели импортируются, базовые constraints/indexes есть.

## Этап 2: Provider Registry И Seed Данных

Цель: API уже должен валидировать `provider_code`, но без реальной отправки.

- Добавить provider abstraction DTO/protocol: `ProviderBatch`, `ProviderMessage`, `ProviderSendResult`, `ProviderMessageSendResult`, `ProviderStatusResult`.
- Добавить registry провайдеров по `code`.
- Добавить fake/in-memory provider adapter для тестов и локального dev.
- Добавить seed или миграционный insert для первого provider config с `max_batch_size`.

Критерий готовности: можно получить список провайдеров и проверить, что неизвестный provider отклоняется.

## Этап 3: API Создания И Чтения Mailing

Цель: сделать основной пользовательский контур без RabbitMQ-отправки.

- Заменить hello-world endpoints в [`/Users/jslv/Documents/projects/sms-gate/app/main.py`](/Users/jslv/Documents/projects/sms-gate/app/main.py) на подключение routers.
- Добавить Pydantic schemas для `POST /sms/mailings`, `GET /sms/mailings/{mailing_id}`, `GET /sms/mailings/{mailing_id}/messages`, `GET /sms/messages/{message_id}`, `GET /providers`.
- Реализовать создание `mailing` в одной DB transaction: validate provider, reject `provider_code = "auto"`, create mailing, messages, batches.
- Пока вместо реальной публикации в RabbitMQ можно помечать batch как `queued` и оставить publisher interface заглушкой, чтобы API-контракт стабилизировался.

Критерий готовности: одиночная SMS создается как mailing из одного message; batch splitting работает; статусы читаются через API.

## Этап 4: RabbitMQ Publisher И Topology

Цель: отделить HTTP API от фоновой отправки.

- Описать `sms.send.x`, `sms.send.q`, `sms.send.retry.q`, `sms.send.dlq`, `sms.status.x`, `sms.status.q`, `sms.status.retry.q`, `sms.status.dlq`.
- Реализовать aio-pika connection/channel/topology setup.
- Добавить publisher задач с payload только из идентификаторов: `batch_id`, `mailing_id`, `provider_code`, `correlation_id`.
- Подключить публикацию send task после успешного создания mailing.

Критерий готовности: создание mailing публикует batch tasks, RabbitMQ management показывает очереди и сообщения.

## Этап 5: Send Worker И Первый Adapter

Цель: реально отправлять batch через provider abstraction.

- Реализовать первый HTTP provider adapter или fake adapter, если реальных credentials/API пока нет.
- Реализовать send worker: consume `sms.send.q`, load batch/messages, check idempotency, call adapter, save `provider_dispatches`, update `sms_messages.provider_message_id`, update statuses, ack only after DB commit.
- Добавить retry/DLQ policy для temporary/permanent provider errors.
- Сохранять raw response ограниченно, без секретов.

Критерий готовности: worker обрабатывает batch, статусы сообщений переходят в `submitted`/`failed`, повторная доставка не создает дубль отправки.

## Этап 6: Status Worker И Агрегация Статусов

Цель: polling статусов и корректный aggregate status mailing.

- Реализовать status task publishing после successful submit.
- Реализовать status worker: consume `sms.status.q`, call adapter status API, normalize provider status, save `status_checks`, update messages/batches/mailings.
- Добавить функцию агрегации mailing status из статусов сообщений.
- Добавить retry для transient status errors.

Критерий готовности: submitted messages доходят до финальных normalized статусов, mailing показывает агрегированный статус.

## Этап 7: Idempotency И Базовая User/Auth Модель

Цель: закрыть риск дублей от ERP retries и подготовить разграничение доступа.

- Добавить dependency текущего пользователя. Для MVP можно начать с простого header/API-key механизма, без OAuth/JWT.
- Добавить `source`: `ui`/`erp`, `created_by` и technical ERP user.
- Реализовать `Idempotency-Key`: request hash, stored response, replay duplicate response, conflict on same key with different body.
- Ограничить чтение mailings/messages текущим user scope.

Критерий готовности: повтор `POST /sms/mailings` с тем же ключом не создает новую рассылку.

## Этап 8: Тесты И Минимальная Наблюдаемость

Цель: закрепить критичные инварианты перед расширением.

- Добавить тесты на создание mailing, single SMS, batch splitting, provider validation, custom_id mapping, idempotency, worker idempotency, retry branches.
- Добавить structured logs с correlation id.
- Добавить provider request/response logging без secrets.
- README обновить командами: поднять infra, применить миграции, запустить API, запустить workers, прогнать тесты.

Критерий готовности: test suite проходит локально, руками можно пройти полный path create -> queue -> send worker -> status read.

## Порядок Старта

Начинаем с Этапа 0 и Этапа 1. Это самый короткий путь к нормальной базе для дальнейших вертикальных фич: без БД и миграций API/worker быстро превратятся в временные заглушки.

Первый рабочий кусок после принятия плана:

1. Починить структуру проекта и зависимости.
2. Заполнить compose для Postgres/RabbitMQ.
3. Добавить config/db/session.
4. Настроить Alembic.
5. Создать первую схему моделей и миграцию.

После этого уже можно идти в Этап 3 и делать `POST /sms/mailings` без реальной отправки.