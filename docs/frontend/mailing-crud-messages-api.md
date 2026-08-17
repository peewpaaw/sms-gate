# Рассылки и сообщения (CRUD API)

Документ для интеграции UI: создание и редактирование `mailing`, вложенный CRUD `message`, ограничения по статусам, коды ошибок.

Актуально для API с nested routes `/mailings/{id}/messages` и частичным `PUT /mailings/{id}`.

## Общее

- **Base path:** `/api/v1`
- **Аутентификация:** HTTP Basic (`Authorization: Basic …`, username = email). Профиль: [`GET /users/me/`](./users-basic-auth-api.md)
- **OpenAPI tag:** `mailings`
- **Провайдеры:** см. [4d183d1-provider-api.md](./4d183d1-provider-api.md) — `GET /providers/`, `provider_code` при создании/обновлении рассылки

---

## Статусы (enum в JSON)

**Рассылка (`mailing.status`):**

| Значение | Смысл для UI |
|----------|----------------|
| `created` | Черновик: можно менять рассылку и сообщения (см. правила ниже) |
| `queued` | Отправка поставлена в очередь |
| `submitted` | Передано провайдеру (агрегат по рассылке) |

**Сообщение (`message.status`):**

| Значение | Смысл |
|----------|--------|
| `created` | Можно редактировать/удалять через nested API |
| `queued`, `submitted`, `delivered`, `undelivered`, `failed`, `unknown` | Только просмотр; мутации → **409** |

**Правило для кнопок в UI:** блокировать редактирование рассылки и сообщений, если `mailing.status !== 'created'`. Для PUT/DELETE отдельного message дополнительно требовать `message.status === 'created'`.

---

## Модели (кратко)

### Создание сообщения / тело message

```json
{
  "msisdn": "+375 29 1234567",
  "text": "Текст SMS",
  "send_on": "2026-07-08T12:00:00+03:00"
}
```

| Поле | Ограничения |
|------|-------------|
| `msisdn` | 9–16 символов; пробелы и `+` убираются, в ответе — только цифры |
| `text` | 1–1600 символов |
| `send_on` | опционально, ISO 8601 с timezone |

### `MailingRead` (ответ GET/POST/PUT рассылки)

```json
{
  "id": "uuid",
  "status": "created",
  "messages": [ { "...": "MessageRead" } ],
  "created_by": { "id": "uuid", "is_active": true, "name": "", "email": "...", "role": "user" },
  "updated_by": { "id": "uuid", "is_active": true, "name": "", "email": "...", "role": "user" },
  "created_at": "...",
  "updated_at": "..."
}
```

`MessageRead`: `id`, `msisdn`, `text`, `send_on`, `external_id`, `status`, `batch_id`.

> **Замечание:** в текущем `MailingRead` нет поля `provider_code`. Для отображения провайдера после GET храните выбранный код на клиенте или запрашивайте доработку API.

---

## Рассылка (`/mailings`)

### `GET /api/v1/mailings/`

Пагинация + фильтр по статусу рассылки.

| Query | Default | Описание |
|-------|---------|----------|
| `status` | — | `created` \| `queued` \| `submitted` |
| `limit` | 50 | 1–500 |
| `offset` | 0 | |

Ответ: `Page[MailingRead]` — `{ total, limit, offset, items }`.

### `POST /api/v1/mailings/`

Создание рассылки.

```json
{
  "provider_code": "fake",
  "messages": []
}
```

- `messages` **может быть пустым** `[]` — дальше получатели добавляются через `POST .../messages/`.
- Ответ **200** + `MailingRead`.
- **422** по провайдеру: см. provider-api (`Unknown provider`, `Provider disabled`, `Provider is not configured on this server`).

### `GET /api/v1/mailings/{mailing_id}`

Одна рассылка со всеми вложенными `messages`.

**404:** `Mailing not found`

### `PUT /api/v1/mailings/{mailing_id}`

Обновление только при `mailing.status === 'created'`.

```json
{
  "provider_code": "fake"
}
```

| Поле в body | Поведение |
|-------------|-----------|
| `provider_code` | обязательное |
| `messages` **отсутствует** | список сообщений **не меняется** |
| `messages: []` | **полная очистка** всех message (старые id удаляются) |
| `messages: [ {...}, ... ]` | **полная замена** списка (как при create, новые id у message) |

Не отправляйте `messages: null` — семантика не задокументирована; используйте отсутствие ключа или `[]`.

**409:** `Mailing can be updated only in created status`  
**404 / 422:** как у POST.

### `DELETE /api/v1/mailings/{mailing_id}`

Только при `mailing.status === 'created'`.

**204** без тела.  
**404:** `Mailing not found`  
**409:** `Mailing can be deleted only in created status`

### `POST /api/v1/mailings/{mailing_id}/send`

Запуск отправки (батчи, очередь). Не входит в CRUD редактирования; после успеха статусы уходят из `created`.

**200:** `{ "message": "Mailing batched" }`  
**404:** `Mailing not found`

---

## Сообщения внутри рассылки (`/mailings/{mailing_id}/messages`)

Базовый path: `/api/v1/mailings/{mailing_id}/messages`

### `POST .../messages/` — добавить получателя

> **Важно:** trailing slash обязателен (`.../messages/`), иначе FastAPI отвечает **307** redirect.

Тело: как `MessageCreate` (один объект).

**201** + `MessageRead`.  
**404:** `Mailing not found`  
**409:** `Mailing can be updated only in created status` (рассылка не в `created`)

### `GET .../messages/{message_id}`

Одно сообщение; проверяется принадлежность к `mailing_id`.

**404:** `Message not found` (в т.ч. id из другой рассылки)

### `PUT .../messages/{message_id}`

Полная замена полей (`msisdn`, `text`, `send_on`) — тело как при создании.

Условия: `mailing.status === 'created'` **и** `message.status === 'created'`.

**200** + `MessageRead`.  
**404:** `Mailing not found` \| `Message not found`  
**409:**  
- `Mailing can be updated only in created status`  
- `Message can be modified only in created status`

### `DELETE .../messages/{message_id}`

Условия те же, что у PUT message.

**204** без тела.  
**404 / 409:** как у PUT message.

---

## Сценарии UI

| Задача | Рекомендуемый API |
|--------|-------------------|
| Мастер «сначала рассылка, потом получатели» | `POST /mailings/` с `messages: []`, затем `POST .../messages/` на каждую строку |
| Смена только провайдера | `PUT /mailings/{id}` с `{ "provider_code": "..." }` **без** ключа `messages` |
| Массовая замена списка получателей | `PUT /mailings/{id}` с полным массивом `messages` **или** цикл nested CRUD |
| Редактирование одной строки таблицы | `PUT .../messages/{message_id}` |
| Удаление одной строки | `DELETE .../messages/{message_id}` |
| Просмотр после отправки | `GET` рассылки/сообщения; кнопки Save/Delete скрыть при `status !== 'created'` |

Список всех сообщений рассылки: **`GET /mailings/{id}`** (отдельного list-endpoint для messages нет).

---

## Сводка HTTP-ошибок (mailings + messages)

| HTTP | `detail` | Когда |
|------|----------|--------|
| 401 | `Unauthorized` | Нет/неверный Basic Auth |
| 404 | `Mailing not found` | Нет рассылки |
| 404 | `Message not found` | Нет message или не тот `mailing_id` |
| 409 | `Mailing can be updated only in created status` | Мутация рассылки/message при статусе рассылки ≠ `created` |
| 409 | `Mailing can be deleted only in created status` | DELETE рассылки |
| 409 | `Message can be modified only in created status` | PUT/DELETE message при `message.status` ≠ `created` |
| 422 | validation / provider | Pydantic или провайдер |

---

## Swagger

`/docs` → тег **mailings**: методы рассылки и вложенные `messages` под тем же тегом.
