# Коммит `4d183d1` — каталог SMS-провайдеров (API)

**Commit:** `4d183d1e08704c8b13e2c792cabda5fa809b9e06`  
**Сообщение:** `provider api added`

Документ для интеграции UI: выбор провайдера при создании рассылки, админка включения/выключения, обработка ошибок.

## Общее

- **Base path:** `/api/v1`
- **Аутентификация:** заголовок `X-API-Key` (как у остальных методов).
- **OpenAPI tag:** `providers`

## Breaking change: `GET /providers/`

Раньше ответ был списком кодов (`items: string[]`). Теперь — объекты с метаданными.

### `GET /api/v1/providers/`

Список провайдеров для селекта при создании рассылки.

| Query | Тип | Default | Описание |
|-------|-----|---------|----------|
| `enabled_only` | boolean | `true` | `true` — только `is_enabled=true` и только те, у кого на сервере есть реализация (адаптер). `false` — все строки из БД, в т.ч. выключенные; без адаптера `max_batch_size` может быть `0`. |

**Ответ 200:**

```json
{
  "items": [
    {
      "code": "beltelecom",
      "name": "Белтелеком",
      "is_enabled": true,
      "max_batch_size": 1
    },
    {
      "code": "fake",
      "name": "Fake (dev)",
      "is_enabled": true,
      "max_batch_size": 1
    }
  ]
}
```

| Поле | Назначение для UI |
|------|-------------------|
| `code` | Значение для `POST /mailings` → `provider_code` |
| `name` | Подпись в селекте |
| `is_enabled` | При `enabled_only=false` можно показать «выключен» в админке |
| `max_batch_size` | Лимит размера batch у провайдера (для подсказок/валидации на клиенте — опционально) |

**Рекомендация:** для формы создания рассылки вызывать без параметров (`enabled_only=true`) и показывать `name`, в payload отправлять `code`.

---

### `PATCH /api/v1/providers/{code}`

Частичное обновление записи в каталоге (имя, доступность для **новых** рассылок).

**Path:** `code` — тот же идентификатор, что в `GET` (`fake`, `beltelecom`, …).

**Body (JSON):** хотя бы одно поле обязательно.

```json
{ "name": "Белтелеком SMS", "is_enabled": false }
```

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | string, 1–255 | Отображаемое имя |
| `is_enabled` | boolean | `false` — провайдер пропадает из списка при `enabled_only=true` и блокирует новые рассылки |

**Ответ 200:** один объект `ProviderRead` (те же поля, что элемент `items` в GET).

**Ошибки:**

| HTTP | `detail` | Когда |
|------|----------|--------|
| 404 | `Provider not found` | Нет такого `code` в БД |
| 422 | `At least one of name or is_enabled must be set` | Пустой body |

Выключение провайдера **не отменяет** уже созданные рассылки и не блокирует отправку уже поставленных в очередь.

---

## Изменения при создании рассылки

### `POST /api/v1/mailings/`

Тело без изменений: `provider_code` + `messages[]`.

Добавлена серверная проверка:

1. Код есть в таблице `provider`.
2. `is_enabled === true`.
3. На сервере зарегистрирован адаптер для этого кода.

**Новые ответы 422** (раньше мог пройти любой строковый код):

| `detail` | Смысл для UI |
|----------|----------------|
| `Unknown provider` | Нет в каталоге |
| `Provider disabled` | Есть, но выключен (`PATCH` / админка) |
| `Provider is not configured on this server` | В БД есть, на инстансе нет реализации |

**UI:** список кодов брать только из `GET /providers/`; при 422 показывать текст `detail` или локализованные сообщения по этим строкам.

---

## Миграция БД (инфра)

Для локального/staging окружения нужен `alembic upgrade head` (таблица `provider`, seed `fake` / `beltelecom`, FK с `mailing` / `messages_batch`). Без миграции API провайдеров и create mailing могут падать на уровне БД.

---

## Swagger

После деплоя: `/docs` → тег **providers**. Тип ответа `GET /providers/` — `ProviderListResponse`, не `list[str]`.
